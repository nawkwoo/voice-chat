"""
대화 서비스
"""

import uuid
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.database.models import ConversationSession, ConversationMessage, User
from app.vector_store.milvus_client import MilvusVectorStore
from app.utils.logging import get_logger

logger = get_logger("conversation_service")


class ConversationService:
    """
    대화 세션 및 메시지 관련 비즈니스 로직을 처리하는 서비스 클래스입니다.
    - 세션 생성, 종료, 조회, 삭제
    - 메시지 추가(MariaDB + Milvus), 조회
    - LLM을 위한 대화 컨텍스트 생성
    - 통계 조회
    """
    
    def __init__(self):
        """
        ConversationService를 초기화합니다.
        필요 시 Milvus 벡터 스토어 클라이언트를 생성하고 연결합니다.
        """
        self.vector_store = None
        try:
            self.vector_store = MilvusVectorStore()
            logger.info("✅ Milvus 벡터 스토어 클라이언트가 성공적으로 초기화되었습니다.")
        except Exception as e:
            logger.warning(f"⚠️ Milvus 벡터 스토어 초기화에 실패했습니다. 벡터 검색 기능이 비활성화됩니다: {e}")
            self.vector_store = None
    
    def create_session(self, db: Session, user_id: str) -> str:
        """
        새로운 대화 세션을 생성합니다.
        - 사용자가 존재하지 않으면 새로 생성합니다.
        - 고유한 세션 ID를 생성하여 데이터베이스에 저장합니다.
        """
        try:
            # 사용자가 데이터베이스에 존재하는지 확인하고, 없으면 새로 추가합니다.
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                user = User(user_id=user_id)
                db.add(user)
                db.commit()
                logger.info(f"데이터베이스에 존재하지 않는 사용자({user_id})를 새로 생성했습니다.")
            
            # 고유한 세션 ID를 생성합니다.
            session_id = f"session_{uuid.uuid4().hex[:8]}"
            session = ConversationSession(
                session_id=session_id,
                user_id=user_id
            )
            
            db.add(session)
            db.commit()
            
            logger.info(f"📋 사용자({user_id})를 위한 새 대화 세션({session_id})을 생성했습니다.")
            return session_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"새로운 세션 생성 중 데이터베이스 오류가 발생했습니다: {e}", exc_info=True)
            raise
    
    def add_message_with_vector(self, db: Session, session_id: str, user_id: str,
                               role: str, content: str, processing_time_ms: int = None) -> str:
        """
        대화 메시지를 MariaDB에 저장하고, 사용자 메시지인 경우 Milvus에도 벡터로 저장합니다.
        - MariaDB: 모든 메시지의 원본 텍스트와 메타데이터를 저장합니다.
        - Milvus: 사용자(user)의 메시지만 임베딩하여 벡터로 저장하여, 추후 유사도 검색에 사용합니다.
        """
        try:
            # --- 1. 세션 제목 자동 생성 (첫 사용자 메시지인 경우) ---
            # session = db.query(ConversationSession).filter(ConversationSession.session_id == session_id).first()
            # # 세션에 제목이 없고, 현재 메시지가 사용자의 메시지일 때 제목을 생성합니다.
            # if session and session.title is None and role == "user":
            #     # 메시지 내용을 20자로 잘라 제목으로 설정
            #     session.title = content[:20]
            #     logger.info(f"세션({session_id})의 제목이 '{session.title}'(으)로 자동 설정되었습니다.")

            message_id = f"msg_{uuid.uuid4().hex[:12]}"
            
            # 1. MariaDB에 메시지 저장
            message = ConversationMessage(
                message_id=message_id,
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=content,
                processing_time_ms=processing_time_ms
            )
            db.add(message)
            db.commit()
            
            # 2. Milvus에 벡터 저장 (사용자 메시지인 경우에만)
            if self.vector_store and role == "user":
                try:
                    created_at = message.created_at.isoformat()
                    self.vector_store.add_vector(
                        message_id, user_id, session_id, content, created_at
                    )
                    logger.info(f"메시지({message_id})의 벡터를 Milvus에 저장했습니다.")
                except Exception as e:
                    logger.warning(f"메시지({message_id})의 벡터를 Milvus에 저장하는 데 실패했습니다: {e}")
            
            logger.debug(f"메시지({message_id})를 MariaDB에 성공적으로 저장했습니다.")
            return message_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 메시지 저장 중 데이터베이스 오류가 발생했습니다: {e}", exc_info=True)
            raise
    
    def get_context_for_llm(self, user_id: str, session_id: str, current_message: str,
                           db: Session, top_k: int = 3, min_score: float = 0.6, session_only: bool = True) -> str:
        """
        LLM에 전달할 대화 컨텍스트를 구성합니다.
        - **최근 대화 (MariaDB)**: 현재 세션의 마지막 몇 개 메시지를 가져와 시간적 연속성을 제공합니다.
        - **관련 대화 (Milvus)**: 현재 메시지와 의미적으로 유사한 과거 메시지를 벡터 검색을 통해 가져와 관련 정보를 제공합니다.
        """
        try:
            context_parts = []
            
            # 1. MariaDB에서 최근 대화 내용 조회
            recent_messages = self.get_recent_conversation(db=db, session_id=session_id, limit=4)
            if recent_messages:
                recent_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_messages])
                context_parts.append(f"### 최근 대화 내용:\n{recent_context}")
            
            # 2. Milvus에서 의미적으로 유사한 대화 내용 검색
            if self.vector_store:
                try:
                    similar_messages = self.vector_store.search_similar(
                        current_message, user_id, session_id if session_only else None,
                        top_k, min_score
                    )
                    if similar_messages:
                        similar_context = "\n".join([f"- {msg['content']}" for msg in similar_messages])
                        context_parts.append(f"### 관련 과거 대화 내용:\n{similar_context}")
                        
                except Exception as e:
                    logger.warning(f"Milvus 벡터 검색 중 오류가 발생했습니다: {e}")
            
            return "\n\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"❌ LLM 컨텍스트 구성 중 오류가 발생했습니다: {e}", exc_info=True)
            return ""
    
    def get_recent_conversation(self, db: Session, session_id: str, limit: int = 4) -> List[Dict]:
        """지정된 세션의 최근 대화 기록을 N개 조회합니다."""
        try:
            messages = db.query(ConversationMessage).filter(
                ConversationMessage.session_id == session_id
            ).order_by(
                desc(ConversationMessage.created_at)
            ).limit(limit).all()
            
            # 결과를 시간 오름차순으로 정렬하여 반환
            return [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "processing_time_ms": msg.processing_time_ms
                }
                for msg in reversed(messages)
            ]
            
        except Exception as e:
            logger.error(f"❌ 최근 대화 기록 조회 중 오류가 발생했습니다 (세션 ID: {session_id}): {e}", exc_info=True)
            return []
    
    def get_session_stats(self, db: Session, session_id: str) -> Optional[Dict]:
        """
        특정 세션의 상세 통계 정보를 조회합니다.
        (메시지 수, 사용자/어시스턴트 발화 수, 평균 처리 시간 등)
        """
        try:
            session = db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id
            ).first()
            
            if not session:
                logger.warning(f"통계 조회 실패: 세션({session_id})을 찾을 수 없습니다.")
                return None
            
            # 메시지 수
            message_count = db.query(ConversationMessage).filter(
                ConversationMessage.session_id == session_id
            ).count()
            
            # 사용자/어시스턴트 메시지 수
            user_messages = db.query(ConversationMessage).filter(
                ConversationMessage.session_id == session_id,
                ConversationMessage.role == "user"
            ).count()
            
            assistant_messages = db.query(ConversationMessage).filter(
                ConversationMessage.session_id == session_id,
                ConversationMessage.role == "assistant"
            ).count()
            
            # 평균 처리 시간
            avg_processing_time = db.query(
                func.avg(ConversationMessage.processing_time_ms)
            ).filter(
                ConversationMessage.session_id == session_id,
                ConversationMessage.processing_time_ms.isnot(None)
            ).scalar()
            
            return {
                "session_id": session_id,
                "user_id": session.user_id,
                "created_at": session.started_at.isoformat(),
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "is_active": not session.ended_at,
                "message_count": message_count,
                "user_messages": user_messages,
                "assistant_messages": assistant_messages,
                "avg_processing_time_ms": float(avg_processing_time) if avg_processing_time is not None else None
            }
            
        except Exception as e:
            logger.error(f"❌ 세션({session_id}) 통계 조회 중 오류가 발생했습니다: {e}", exc_info=True)
            return None
    
    def end_session(self, db: Session, session_id: str):
        """세션을 비활성 상태로 변경하고 종료 시간을 기록합니다."""
        try:
            session = db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id
            ).first()
            
            if session:
                session.is_active = False
                session.ended_at = datetime.utcnow()
                db.commit()
                logger.info(f"세션({session_id})이 성공적으로 종료되었습니다.")
            else:
                logger.warning(f"종료할 세션({session_id})을 찾을 수 없습니다.")
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 세션({session_id}) 종료 중 오류가 발생했습니다: {e}", exc_info=True)
            raise

    def get_sessions_by_user(self, db: Session, user_id: str) -> List[Dict]:
        """특정 사용자의 모든 세션 목록을 최신순으로 조회합니다."""
        try:
            sessions = db.query(ConversationSession).filter(
                ConversationSession.user_id == user_id
            ).order_by(
                desc(ConversationSession.started_at)  # 필드명 오류 수정: created_at -> started_at
            ).all()

            return [
                {
                    "session_id": s.session_id,
                    "user_id": s.user_id,
                    "title": f"대화 {s.id}",
                    "created_at": s.started_at.isoformat(),
                    "message_count": db.query(ConversationMessage).filter(ConversationMessage.session_id == s.session_id).count()
                }
                for s in sessions
            ]
        except Exception as e:
            logger.error(f"❌ 사용자({user_id})의 세션 목록 조회 중 오류가 발생했습니다: {e}", exc_info=True)
            return []

    def get_messages_by_session(self, db: Session, session_id: str) -> List[Dict]:
        """특정 세션의 모든 메시지를 시간순으로 조회합니다."""
        try:
            messages = db.query(ConversationMessage).filter(
                ConversationMessage.session_id == session_id
            ).order_by(
                ConversationMessage.created_at
            ).all()
            
            return [
                {
                    "message_id": msg.message_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }
                for msg in messages
            ]
        except Exception as e:
            logger.error(f"❌ 세션({session_id})의 메시지 조회 중 오류가 발생했습니다: {e}", exc_info=True)
            return []

    def delete_session(self, db: Session, session_id: str):
        """
        세션 및 관련된 모든 메시지를 데이터베이스에서 삭제합니다.
        (주의: 벡터 스토어의 관련 데이터는 별도로 처리해야 할 수 있습니다.)
        """
        try:
            # 관련된 메시지 먼저 삭제 (외래 키 제약 조건)
            db.query(ConversationMessage).filter(ConversationMessage.session_id == session_id).delete(synchronize_session=False)

            # 세션 삭제
            session = db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id
            ).first()
            
            if session:
                db.delete(session)
                db.commit()
                logger.info(f"🗑️ 세션({session_id}) 및 관련 메시지가 성공적으로 삭제되었습니다.")
            else:
                logger.warning(f"삭제할 세션({session_id})을 찾을 수 없습니다.")

        except Exception as e:
            db.rollback()
            logger.error(f"❌ 세션({session_id}) 삭제 중 오류가 발생했습니다: {e}", exc_info=True)
            raise
