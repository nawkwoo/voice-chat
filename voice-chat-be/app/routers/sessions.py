"""
세션 관리 라우터
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.deps import get_db
from app.services.users import create_new_user, get_user_stats
from app.services.conversation import create_session, get_session_stats, end_session, get_conversation_service
from app.utils.logging import get_logger
from app.services.users import UserService

logger = get_logger("sessions")

# --- APIRouter 생성 ---
# "/api/sessions" 접두사와 "sessions" 태그를 사용하여 라우터를 생성합니다.
# 이 라우터는 사용자의 대화 세션과 관련된 모든 API 엔드포인트를 관리합니다.
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/{user_id}")
async def get_user_sessions_endpoint(user_id: str, db: Session = Depends(get_db)):
    """
    특정 사용자의 모든 대화 세션 목록을 조회합니다.
    
    Args:
        user_id (str): 세션 목록을 조회할 사용자의 ID
        db (Session): 데이터베이스 세션
    
    Returns:
        dict: 사용자의 세션 목록
    """
    try:
        service = get_conversation_service()
        sessions = service.get_sessions_by_user(db, user_id)
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"사용자({user_id})의 세션 목록 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@router.get("/{session_id}/messages")
async def get_session_messages_endpoint(session_id: str, db: Session = Depends(get_db)):
    """
    특정 세션에 속한 모든 메시지 기록을 조회합니다.
    
    Args:
        session_id (str): 메시지를 조회할 세션의 ID
        db (Session): 데이터베이스 세션
        
    Returns:
        dict: 세션의 메시지 목록
    """
    try:
        service = get_conversation_service()
        messages = service.get_messages_by_session(db, session_id)
        return {"messages": messages}
    except Exception as e:
        logger.error(f"세션({session_id})의 메시지 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@router.delete("/{session_id}")
async def delete_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    """
    특정 세션을 데이터베이스에서 삭제합니다.
    관련된 메시지 및 벡터 데이터도 함께 삭제될 수 있습니다. (서비스 로직에 따라 다름)
    
    Args:
        session_id (str): 삭제할 세션의 ID
        db (Session): 데이터베이스 세션
        
    Returns:
        dict: 삭제 완료 상태 메시지
    """
    try:
        service = get_conversation_service()
        service.delete_session(db, session_id)
        logger.info(f"세션({session_id})이 성공적으로 삭제되었습니다.")
        return {"status": "deleted", "session_id": session_id}
    except Exception as e:
        logger.error(f"세션({session_id}) 삭제 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@router.post("/new")
async def create_new_session_endpoint(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    새로운 대화 세션을 생성합니다.
    - 요청에 `user_id`가 포함되어 있으면 해당 사용자의 새 세션을 생성합니다.
    - `user_id`가 없으면, 새로운 사용자를 먼저 생성한 후 해당 사용자의 세션을 생성합니다.
    
    Args:
        request (dict): `user_id` (선택 사항)를 포함하는 요청 바디
        db (Session): 데이터베이스 세션
        
    Returns:
        dict: 생성된 사용자 ID와 세션 ID 정보
    """
    try:
        user_id = request.get("user_id")
        
        # 사용자 ID가 제공되지 않은 경우, 새로운 사용자를 생성합니다.
        if not user_id:
            user_service = UserService()
            user_id = user_service.create_new_user(db)
            logger.info(f"새로운 사용자({user_id})가 생성되었습니다.")
        
        # 새로운 대화 세션을 생성합니다.
        session_id = create_session(db, user_id)
        logger.info(f"사용자({user_id})를 위한 새 세션({session_id})이 생성되었습니다.")
        
        return {
            "user_id": user_id,
            "session_id": session_id,
            "status": "created"
        }
        
    except Exception as e:
        logger.error(f"새로운 세션 생성 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@router.get("/{user_id}/stats")
async def get_user_stats_endpoint(user_id: str, db: Session = Depends(get_db)):
    """
    특정 사용자의 통계 정보(예: 총 대화 시간, 세션 수 등)를 조회합니다.
    
    Args:
        user_id (str): 통계를 조회할 사용자의 ID
        db (Session): 데이터베이스 세션
        
    Returns:
        dict: 사용자의 통계 정보
    """
    try:
        stats = get_user_stats(user_id, db)
        if not stats:
            raise HTTPException(status_code=404, detail=f"사용자({user_id})를 찾을 수 없습니다.")
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"사용자({user_id}) 통계 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@router.get("/{session_id}/stats")
async def get_session_stats_endpoint(session_id: str, db: Session = Depends(get_db)):
    """
    특정 세션의 통계 정보(예: 메시지 수, 대화 길이 등)를 조회합니다.
    
    Args:
        session_id (str): 통계를 조회할 세션의 ID
        db (Session): 데이터베이스 세션
        
    Returns:
        dict: 세션의 통계 정보
    """
    try:
        stats = get_session_stats(db, session_id)
        if not stats:
            raise HTTPException(status_code=404, detail=f"세션({session_id})을 찾을 수 없습니다.")
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션({session_id}) 통계 조회 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")


@router.post("/{session_id}/end")
async def end_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    """
    진행 중인 대화 세션을 종료 상태로 변경합니다.
    
    Args:
        session_id (str): 종료할 세션의 ID
        db (Session): 데이터베이스 세션
        
    Returns:
        dict: 종료 완료 상태 메시지
    """
    try:
        end_session(db, session_id)
        logger.info(f"세션({session_id})이 종료되었습니다.")
        return {"status": "ended", "session_id": session_id}
        
    except Exception as e:
        logger.error(f"세션({session_id}) 종료 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")
