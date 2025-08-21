"""
대화 서비스 래퍼
"""

from app.services.conversation_service import ConversationService
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.utils.logging import get_logger

logger = get_logger("conversation")

# 전역 서비스 인스턴스
conversation_service = None


def get_conversation_service() -> ConversationService:
    """대화 서비스 인스턴스를 반환합니다."""
    global conversation_service
    if conversation_service is None:
        try:
            conversation_service = ConversationService()
            logger.info("✅ 대화 서비스 초기화 완료")
        except Exception as e:
            logger.warning(f"⚠️ 대화 서비스 초기화 실패: {e}")
            conversation_service = None
    return conversation_service


def create_session(db: Session, user_id: str) -> str:
    """새 대화 세션 생성"""
    service = get_conversation_service()
    if not service:
        raise Exception("대화 서비스가 초기화되지 않았습니다.")
    
    try:
        return service.create_session(db, user_id)
    except Exception as e:
        logger.error(f"❌ 세션 생성 실패: {e}")
        raise


def add_message_with_vector(db: Session, session_id: str, user_id: str, 
                           role: str, content: str, processing_time_ms: int = None) -> str:
    """메시지를 MariaDB + Milvus에 동시 저장"""
    service = get_conversation_service()
    if not service:
        raise Exception("대화 서비스가 초기화되지 않았습니다.")
    
    try:
        return service.add_message_with_vector(
            db, session_id, user_id, role, content, processing_time_ms
        )
    except Exception as e:
        logger.error(f"❌ 메시지 저장 실패: {e}")
        raise


def get_context_for_llm(user_id: str, session_id: str, current_message: str, 
                       top_k: int = 3, min_score: float = 0.6, 
                       session_only: bool = True) -> str:
    """LLM용 컨텍스트 조회"""
    service = get_conversation_service()
    if not service:
        return ""
    
    try:
        return service.get_context_for_llm(
            user_id, session_id, current_message, top_k, min_score, session_only
        )
    except Exception as e:
        logger.error(f"❌ 컨텍스트 조회 실패: {e}")
        return ""


def get_recent_conversation(db: Session, session_id: str, limit: int = 4) -> List[Dict]:
    """최근 대화 조회"""
    service = get_conversation_service()
    if not service:
        return []
    
    try:
        return service.get_recent_conversation(db, session_id, limit)
    except Exception as e:
        logger.error(f"❌ 최근 대화 조회 실패: {e}")
        return []


def get_session_stats(db: Session, session_id: str) -> Dict:
    """세션 통계 조회"""
    service = get_conversation_service()
    if not service:
        return {}
    
    try:
        return service.get_session_stats(db, session_id)
    except Exception as e:
        logger.error(f"❌ 세션 통계 조회 실패: {e}")
        return {}


def end_session(db: Session, session_id: str):
    """세션 종료"""
    service = get_conversation_service()
    if not service:
        return
    
    try:
        service.end_session(db, session_id)
    except Exception as e:
        logger.error(f"❌ 세션 종료 실패: {e}")
        raise
