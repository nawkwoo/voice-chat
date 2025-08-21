"""
Milvus 벡터 데이터베이스 클라이언트
"""

import os
from typing import List, Dict, Any, Optional
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger("milvus")


class MilvusVectorStore:
    """Milvus 벡터 스토어 클래스"""
    
    def __init__(self):
        self.collection_name = settings.MILVUS_COLLECTION
        self.embedding_model = settings.EMBEDDING_MODEL
        self._sentence_transformer = None
        self._collection = None
        
        # Milvus 연결
        self._connect()
        
        # 컬렉션 초기화
        self._init_collection()
    
    def _connect(self):
        """Milvus 서버 연결"""
        try:
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT
            )
            logger.info("✅ Milvus 연결 성공")
        except Exception as e:
            logger.error(f"❌ Milvus 연결 실패: {e}")
            raise
    
    def _get_sentence_transformer(self):
        """SentenceTransformer 모델 지연 로드"""
        if self._sentence_transformer is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"🔄 임베딩 모델 로드: {self.embedding_model}")
                self._sentence_transformer = SentenceTransformer(self.embedding_model)
                logger.info("✅ 임베딩 모델 로드 완료")
            except Exception as e:
                logger.error(f"❌ 임베딩 모델 로드 실패: {e}")
                raise
        return self._sentence_transformer
    
    def _init_collection(self):
        """컬렉션 초기화"""
        try:
            # 컬렉션이 존재하지 않으면 생성
            if not utility.has_collection(self.collection_name):
                self._create_collection()
            
            # 컬렉션 로드
            self._collection = Collection(self.collection_name)
            self._collection.load()
            logger.info(f"✅ Milvus 컬렉션 로드: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"❌ Milvus 컬렉션 초기화 실패: {e}")
            raise
    
    def _create_collection(self):
        """컬렉션 스키마 생성"""
        try:
            # 필드 정의
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="session_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="message_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),  # sentence-transformers 차원
                FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=50)
            ]
            
            # 스키마 생성
            schema = CollectionSchema(fields, description="음성 대화 벡터 저장소")
            
            # 컬렉션 생성
            collection = Collection(self.collection_name, schema)
            
            # 인덱스 생성
            index_params = {
                "metric_type": "COSINE",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            collection.create_index("embedding", index_params)
            
            logger.info(f"✅ Milvus 컬렉션 생성: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"❌ Milvus 컬렉션 생성 실패: {e}")
            raise
    
    def add_vector(self, message_id: str, user_id: str, session_id: str, 
                   content: str, created_at: str) -> bool:
        """벡터 추가"""
        try:
            # 텍스트 임베딩 생성
            model = self._get_sentence_transformer()
            embedding = model.encode(content).tolist()
            
            # 데이터 삽입
            data = [
                [message_id],
                [user_id],
                [session_id],
                [message_id],
                [content],
                [embedding],
                [created_at]
            ]
            
            self._collection.insert(data)
            logger.debug(f"벡터 추가 완료: {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 벡터 추가 실패: {e}")
            return False
    
    def search_similar(self, query: str, user_id: str = None, session_id: str = None,
                      top_k: int = 3, min_score: float = 0.6) -> List[Dict]:
        """유사한 벡터 검색"""
        try:
            # 쿼리 임베딩 생성
            model = self._get_sentence_transformer()
            query_embedding = model.encode(query).tolist()
            
            # 검색 조건 설정
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
            
            # 필터 조건 (선택적)
            expr = None
            if user_id and session_id:
                expr = f'user_id == "{user_id}" and session_id == "{session_id}"'
            elif user_id:
                expr = f'user_id == "{user_id}"'
            
            # 검색 실행
            results = self._collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["content", "message_id", "user_id", "session_id", "created_at"]
            )
            
            # 결과 처리
            similar_messages = []
            for hits in results:
                for hit in hits:
                    if hit.score >= min_score:
                        similar_messages.append({
                            "content": hit.entity.get("content"),
                            "message_id": hit.entity.get("message_id"),
                            "user_id": hit.entity.get("user_id"),
                            "session_id": hit.entity.get("session_id"),
                            "created_at": hit.entity.get("created_at"),
                            "score": hit.score
                        })
            
            return similar_messages
            
        except Exception as e:
            logger.error(f"❌ 벡터 검색 실패: {e}")
            return []
    
    def health_check(self) -> bool:
        """헬스체크"""
        try:
            # 간단한 연결 확인
            connections.get_connection("default")
            return True
        except Exception as e:
            logger.error(f"❌ Milvus 헬스체크 실패: {e}")
            return False
    
    def get_collection_stats(self) -> Dict:
        """컬렉션 통계"""
        try:
            if not self._collection:
                return {"error": "컬렉션이 로드되지 않음"}
            
            stats = {
                "collection_name": self.collection_name,
                "num_entities": self._collection.num_entities,
                "is_empty": self._collection.is_empty
            }
            return stats
            
        except Exception as e:
            logger.error(f"❌ 컬렉션 통계 조회 실패: {e}")
            return {"error": str(e)}
