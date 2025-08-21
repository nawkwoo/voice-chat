"""
사용자 서비스 래퍼
"""

from app.services.user_service import UserService
from app.utils.logging import get_logger

logger = get_logger("users")

# 전역 서비스 인스턴스
user_service = None


def get_user_service() -> UserService:
    """사용자 서비스 인스턴스를 반환합니다."""
    global user_service
    if user_service is None:
        try:
            user_service = UserService()
            logger.info("✅ 사용자 서비스 초기화 완료")
        except Exception as e:
            logger.error(f"❌ 사용자 서비스 초기화 실패: {e}")
            raise
    return user_service


def create_new_user() -> str:
    """새 사용자 생성"""
    service = get_user_service()
    try:
        return service.create_new_user()
    except Exception as e:
        logger.error(f"❌ 사용자 생성 실패: {e}")
        raise


def get_user(user_id: str, db):
    """사용자 조회"""
    service = get_user_service()
    try:
        return service.get_user(user_id, db)
    except Exception as e:
        logger.error(f"❌ 사용자 조회 실패: {e}")
        raise


def get_user_stats(user_id: str, db) -> dict:
    """사용자 통계 정보"""
    service = get_user_service()
    try:
        return service.get_user_stats(user_id, db)
    except Exception as e:
        logger.error(f"❌ 사용자 통계 조회 실패: {e}")
        return {}
