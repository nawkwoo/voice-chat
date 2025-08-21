"""
대화 서비스 (Conversation Service)

이 모듈은 대화의 전체 생명주기를 관리하는 핵심 비즈니스 로직을 포함합니다.
- 대화 세션의 생성, 조회, 종료
- 대화 메시지의 저장 (in MariaDB) 및 벡터화 (in Milvus)
- LLM에 전달할 컨텍스트(맥락) 생성
- 통계 정보 조회
"""

import uuid
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.database.models import ConversationSession, ConversationMessage, User
from app.vector_store.milvus_client import MilvusVectorStore
from app.utils.logging import get_logger
from fastapi import Depends
from app.database.database import get_db

logger = get_logger("conversation_service")


class ConversationService:
    """
    대화와 관련된 모든 비즈니스 로직을 캡슐화하는 서비스 클래스입니다.
    """

    def __init__(self, db: Session):
        """
        ConversationService 인스턴스를 초기화합니다.

        Args:
            db (Session): 이 서비스 인스턴스에서 사용할 SQLAlchemy 데이터베이스 세션입니다.
                          요청 생명주기 동안 동일한 세션을 사용하여 트랜잭션 일관성을 보장합니다.
        """
        self.db = db
        self.vector_store = self._init_vector_store()

    def _init_vector_store(self) -> Optional[MilvusVectorStore]:
        """Milvus 벡터 스토어 클라이언트를 안전하게 초기화합니다."""
        try:
            vector_store = MilvusVectorStore()
            logger.info("✅ Milvus 벡터 스토어 클라이언트가 성공적으로 초기화되었습니다.")
            return vector_store
        except Exception as e:
            logger.warning(f"⚠️ Milvus 벡터 스토어 초기화 실패. 벡터 검색 기능이 비활성화됩니다: {e}")
            return None

    def create_session(self, user_id: str) -> ConversationSession:
        """
        사용자를 위한 새로운 대화 세션을 생성하고 데이터베이스에 저장합니다.

        - 주어진 `user_id`를 가진 사용자가 없으면 새로 생성합니다.
        - 고유한 `session_id`를 생성하여 새로운 대화 세션을 만듭니다.

        Args:
            user_id (str): 세션을 생성할 사용자의 ID.

        Returns:
            ConversationSession: 새로 생성된 SQLAlchemy 세션 객체.
        """
        try:
            # 사용자가 DB에 존재하는지 확인하고, 없으면 새로 추가합니다.
            user = self.db.query(User).filter(User.user_id == user_id).first()
            if not user:
                user = User(user_id=user_id)
                self.db.add(user)
                self.db.commit()
                logger.info(f"새로운 사용자 '{user_id}'를 생성했습니다.")

            # 새로운 세션 객체를 생성합니다.
            session = ConversationSession(
                session_id=f"session_{uuid.uuid4().hex[:8]}",
                user_id=user_id
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session) # 생성된 세션 객체의 모든 필드(특히 자동 생성된 ID)를 업데이트합니다.

            logger.info(f"📋 사용자 '{user_id}'를 위한 새 대화 세션 '{session.session_id}'을 생성했습니다.")
            return session

        except Exception as e:
            self.db.rollback()
            logger.error(f"세션 생성 중 데이터베이스 오류 발생: {e}", exc_info=True)
            raise  # 오류를 상위로 전파하여 API 레벨에서 처리하도록 합니다.

    def add_message(self, session_id: str, role: str, content: str, processing_time_ms: Optional[int] = None) -> ConversationMessage:
        """
        대화 메시지를 MariaDB에 저장하고, 사용자 메시지인 경우 Milvus에도 벡터로 저장합니다.

        - **MariaDB**: 모든 메시지의 원본 텍스트와 메타데이터를 저장합니다.
        - **Milvus**: 'user' 역할의 메시지만 임베딩하여 벡터로 저장하여, 추후 유사도 검색에 사용합니다.

        Args:
            session_id (str): 메시지가 속한 세션의 ID.
            role (str): 메시지 발화자의 역할 ('user' 또는 'assistant').
            content (str): 메시지의 텍스트 내용.
            processing_time_ms (Optional[int]): 해당 메시지를 생성/처리하는 데 걸린 시간(ms).

        Returns:
            ConversationMessage: 새로 생성된 SQLAlchemy 메시지 객체.
        """
        try:
            session = self.db.query(ConversationSession).filter(ConversationSession.session_id == session_id).first()
            if not session:
                raise ValueError(f"세션 ID '{session_id}'를 찾을 수 없습니다.")

            # 1. MariaDB에 메시지 저장
            message = ConversationMessage(
                message_id=f"msg_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                user_id=session.user_id,
                role=role,
                content=content,
                processing_time_ms=processing_time_ms
            )
            self.db.add(message)
            self.db.commit()
            self.db.refresh(message)

            # 2. Milvus에 벡터 저장 (사용자 메시지이고 벡터 스토어가 활성화된 경우)
            if self.vector_store and role == "user":
                try:
                    created_at_iso = message.created_at.isoformat()
                    self.vector_store.add_vector(
                        message.message_id, session.user_id, session_id, content, created_at_iso
                    )
                    logger.info(f"메시지 '{message.message_id}'의 벡터를 Milvus에 저장했습니다.")
                except Exception as e:
                    logger.warning(f"메시지 '{message.message_id}'의 벡터 저장 실패: {e}")

            logger.debug(f"메시지 '{message.message_id}'를 MariaDB에 성공적으로 저장했습니다.")
            return message

        except Exception as e:
            self.db.rollback()
            logger.error(f"메시지 저장 중 데이터베이스 오류 발생: {e}", exc_info=True)
            raise

    def get_context_for_llm(self, session_id: str, current_message: str, top_k: int = 3) -> str:
        """
        LLM에 전달할 풍부한 대화 컨텍스트(맥락)를 구성합니다.

        컨텍스트는 두 부분으로 구성됩니다:
        1.  **최근 대화 (시간적 맥락)**: 현재 세션의 마지막 N개 메시지를 가져와 대화의 흐름을 파악합니다.
        2.  **관련 대화 (의미적 맥락)**: 현재 메시지와 의미적으로 유사한 과거 메시지를
            벡터 검색(in Milvus)을 통해 가져와 관련 정보를 보강합니다.

        Args:
            session_id (str): 현재 대화 세션의 ID.
            current_message (str): 사용자의 현재 입력 메시지.
            top_k (int): 벡터 검색 시 가져올 유사 메시지의 수.

        Returns:
            str: LLM 프롬프트에 포함될 컨텍스트 문자열.
        """
        try:
            session = self.db.query(ConversationSession).filter(ConversationSession.session_id == session_id).first()
            if not session:
                return "" # 세션이 없으면 컨텍스트도 없음

            context_parts = []

            # 1. MariaDB에서 최근 대화 내용 조회
            recent_messages = self._get_recent_messages(session_id, limit=4)
            if recent_messages:
                recent_context = "\n".join([f"{msg.role}: {msg.content}" for msg in recent_messages])
                context_parts.append(f"### 최근 대화 내용:\n{recent_context}")

            # 2. Milvus에서 의미적으로 유사한 대화 내용 검색
            if self.vector_store:
                try:
                    similar_messages = self.vector_store.search_similar(
                        query_text=current_message,
                        user_id=session.user_id,
                        top_k=top_k
                    )
                    if similar_messages:
                        similar_context = "\n".join([f"- {msg['content']}" for msg in similar_messages])
                        context_parts.append(f"### 관련 과거 대화 내용:\n{similar_context}")
                except Exception as e:
                    logger.warning(f"Milvus 벡터 검색 중 오류 발생: {e}")

            return "\n\n".join(context_parts)

        except Exception as e:
            logger.error(f"LLM 컨텍스트 구성 중 오류 발생: {e}", exc_info=True)
            return "" # 오류 발생 시 빈 컨텍스트 반환

    def _get_recent_messages(self, session_id: str, limit: int = 4) -> List[ConversationMessage]:
        """지정된 세션의 최근 메시지를 DB에서 조회합니다 (내부 헬퍼 함수)."""
        messages = self.db.query(ConversationMessage).filter(
            ConversationMessage.session_id == session_id
        ).order_by(
            desc(ConversationMessage.created_at)
        ).limit(limit).all()
        return list(reversed(messages)) # 시간 순서(오름차순)로 뒤집어서 반환

    def end_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        지정된 세션을 비활성 상태로 변경하고 종료 시간을 기록합니다.

        Args:
            session_id (str): 종료할 세션의 ID.

        Returns:
            Optional[ConversationSession]: 업데이트된 세션 객체. 세션을 찾지 못하면 None.
        """
        try:
            session = self.db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id,
                ConversationSession.ended_at.is_(None) # 이미 종료되지 않은 세션만
            ).first()

            if session:
                session.ended_at = datetime.utcnow()
                self.db.commit()
                self.db.refresh(session)
                logger.info(f"세션 '{session_id}'이 성공적으로 종료되었습니다.")
                return session
            else:
                logger.warning(f"종료할 활성 세션 '{session_id}'을(를) 찾을 수 없습니다.")
                return None

        except Exception as e:
            self.db.rollback()
            logger.error(f"세션 '{session_id}' 종료 중 오류 발생: {e}", exc_info=True)
            raise

    def get_session_stats(self, session_id: str) -> Optional[Dict]:
        """
        특정 세션의 상세 통계 정보를 조회합니다.
        (메시지 수, 사용자/어시스턴트 발화 수, 평균 처리 시간 등)
        """
        try:
            session = self.db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id
            ).first()
            
            if not session:
                logger.warning(f"통계 조회 실패: 세션({session_id})을 찾을 수 없습니다.")
                return None
            
            # 메시지 수
            message_count = self.db.query(ConversationMessage).filter(
                ConversationMessage.session_id == session_id
            ).count()
            
            # 사용자/어시스턴트 메시지 수
            user_messages = self.db.query(ConversationMessage).filter(
                ConversationMessage.session_id == session_id,
                ConversationMessage.role == "user"
            ).count()
            
            assistant_messages = self.db.query(ConversationMessage).filter(
                ConversationMessage.session_id == session_id,
                ConversationMessage.role == "assistant"
            ).count()
            
            # 평균 처리 시간
            avg_processing_time = self.db.query(
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

    def get_sessions_by_user(self, user_id: str) -> List[Dict]:
        """특정 사용자의 모든 세션 목록을 최신순으로 조회합니다."""
        try:
            sessions = self.db.query(ConversationSession).filter(
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
                    "message_count": self.db.query(ConversationMessage).filter(ConversationMessage.session_id == s.session_id).count()
                }
                for s in sessions
            ]
        except Exception as e:
            logger.error(f"❌ 사용자({user_id})의 세션 목록 조회 중 오류가 발생했습니다: {e}", exc_info=True)
            return []

    def get_messages_by_session(self, session_id: str) -> List[Dict]:
        """특정 세션의 모든 메시지를 시간순으로 조회합니다."""
        try:
            messages = self.db.query(ConversationMessage).filter(
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

    def delete_session(self, session_id: str):
        """
        세션 및 관련된 모든 메시지를 데이터베이스에서 삭제합니다.
        (주의: 벡터 스토어의 관련 데이터는 별도로 처리해야 할 수 있습니다.)
        """
        try:
            # 관련된 메시지 먼저 삭제 (외래 키 제약 조건)
            self.db.query(ConversationMessage).filter(ConversationMessage.session_id == session_id).delete(synchronize_session=False)

            # 세션 삭제
            session = self.db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id
            ).first()
            
            if session:
                self.db.delete(session)
                self.db.commit()
                logger.info(f"🗑️ 세션({session_id}) 및 관련 메시지가 성공적으로 삭제되었습니다.")
            else:
                logger.warning(f"삭제할 세션({session_id})을 찾을 수 없습니다.")

        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ 세션({session_id}) 삭제 중 오류가 발생했습니다: {e}", exc_info=True)
            raise

# --- 서비스 인스턴스 관리 ---
# 서비스의 상태가 DB 세션에 의존하므로, 전역 인스턴스 대신
# 요청마다 DB 세션과 함께 생성하는 것이 좋습니다.
# 아래 헬퍼 함수는 라우터에서 의존성 주입을 통해 서비스를 쉽게 가져올 수 있도록 돕습니다.

def get_conversation_service(db: Session = Depends(get_db)) -> ConversationService:
    """FastAPI 의존성 주입을 통해 ConversationService 인스턴스를 생성하여 제공합니다."""
    return ConversationService(db)
