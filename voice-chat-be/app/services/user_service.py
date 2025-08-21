"""
사용자 서비스
"""

import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.models import User, ConversationSession, ConversationMessage
from app.utils.logging import get_logger

logger = get_logger("user_service")


class UserService:
    """
    사용자 관련 비즈니스 로직을 처리하는 서비스 클래스입니다.
    - 신규 사용자 생성
    - 사용자 조회 또는 생성 (Get or Create)
    - 사용자 정보 및 통계 조회
    """
    
    def __init__(self):
        """UserService를 초기화합니다."""
        logger.info("✅ 사용자 서비스(UserService)가 초기화되었습니다.")
    
    def create_new_user(self, db: Session) -> str:
        """
        고유한 ID를 가진 새로운 사용자를 생성하고 데이터베이스에 저장합니다.
        사용자 ID는 타임스탬프와 UUID를 조합하여 생성되므로 충돌 가능성이 거의 없습니다.
        
        Args:
            db (Session): 데이터베이스 세션
            
        Returns:
            str: 새로 생성된 사용자의 고유 ID
        """
        try:
            # 고유성 보장을 위해 현재 타임스탬프와 UUID의 일부를 조합하여 사용자 ID 생성
            user_id = f"user_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
            
            user = User(user_id=user_id)
            db.add(user)
            db.commit()
            db.refresh(user) # 데이터베이스에서 생성된 정보를 객체에 반영
            
            logger.info(f"새로운 사용자({user_id})를 성공적으로 생성했습니다.")
            return user_id
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 새로운 사용자 생성 중 오류가 발생했습니다: {e}", exc_info=True)
            raise
    
    def get_or_create_user(self, user_id: str, db: Session) -> User:
        """
        주어진 ID의 사용자를 조회하고, 존재하지 않을 경우 새로 생성합니다.
        
        Args:
            user_id (str): 조회 또는 생성할 사용자의 ID
            db (Session): 데이터베이스 세션
            
        Returns:
            User: 조회되거나 새로 생성된 User ORM 객체
        """
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                logger.info(f"사용자({user_id})가 존재하지 않아 새로 생성합니다.")
                user = User(user_id=user_id)
                db.add(user)
                db.commit()
                db.refresh(user)
            return user
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ 사용자({user_id}) 조회 또는 생성 중 오류가 발생했습니다: {e}", exc_info=True)
            raise
    
    def get_user(self, user_id: str, db: Session) -> User:
        """
        주어진 ID의 사용자를 조회합니다. 존재하지 않으면 예외를 발생시킵니다.
        
        Args:
            user_id (str): 조회할 사용자의 ID
            db (Session): 데이터베이스 세션
        
        Returns:
            User: 조회된 User ORM 객체
        
        Raises:
            ValueError: 사용자를 찾을 수 없을 때 발생
        """
        try:
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                raise ValueError(f"사용자 ID '{user_id}'에 해당하는 사용자를 찾을 수 없습니다.")
            return user
            
        except Exception as e:
            logger.error(f"❌ 사용자({user_id}) 조회 중 오류가 발생했습니다: {e}", exc_info=True)
            raise
    
    def get_user_stats(self, user_id: str, db: Session) -> dict:
        """
        특정 사용자에 대한 다양한 통계 정보를 계산하여 반환합니다.
        (총 세션 수, 활성 세션 수, 총 메시지 수, 최근 활동 시간 등)
        
        Args:
            user_id (str): 통계를 조회할 사용자의 ID
            db (Session): 데이터베이스 세션
            
        Returns:
            dict: 사용자의 통계 정보를 담은 딕셔너리. 사용자를 찾지 못하면 빈 딕셔너리 반환.
        """
        try:
            # 사용자 존재 여부 확인
            user = self.get_user(user_id, db)
            if not user:
                return {}
            
            # 이 사용자가 생성한 총 세션 수 계산
            session_count = db.query(ConversationSession).filter(
                ConversationSession.user_id == user_id
            ).count()
            
            # 현재 활성 상태(종료되지 않은)인 세션 수 계산
            active_session_count = db.query(ConversationSession).filter(
                ConversationSession.user_id == user_id,
                ConversationSession.is_active == True
            ).count()
            
            # 이 사용자가 주고받은 총 메시지 수 계산
            total_messages = db.query(ConversationMessage).join(
                ConversationSession
            ).filter(
                ConversationSession.user_id == user_id
            ).count()
            
            # 이 사용자의 마지막 메시지 시간(최근 활동 시간) 조회
            latest_activity = db.query(
                func.max(ConversationMessage.created_at)
            ).join(
                ConversationSession
            ).filter(
                ConversationSession.user_id == user_id
            ).scalar()
            
            return {
                "user_id": user_id,
                "created_at": user.created_at.isoformat(),
                "session_count": session_count,
                "active_session_count": active_session_count,
                "total_messages": total_messages,
                "latest_activity": latest_activity.isoformat() if latest_activity else None
            }
            
        except ValueError as e:
            # get_user에서 사용자를 찾지 못해 발생한 예외
            logger.warning(f"통계 조회 실패: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ 사용자({user_id}) 통계 조회 중 오류가 발생했습니다: {e}", exc_info=True)
            return {}
