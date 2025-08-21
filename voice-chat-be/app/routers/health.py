"""
헬스체크 라우터

이 모듈은 애플리케이션의 상태를 외부에 알리는 API 엔드포인트를 정의합니다.
- 간단한 서버 동작 확인 (Ping)
- 연결된 서비스(DB, Vector Store 등)의 상태 점검 (Health Check)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.deps import get_db
from app.database.session import health_check as db_health_check
from app.utils.logging import get_logger
from app.vector_store.milvus_client import MilvusVectorStore

logger = get_logger("health")

# --- APIRouter 생성 ---
# 태그는 API 문서(Swagger UI)에서 엔드포인트들을 그룹화하는 데 사용됩니다.
router = APIRouter()


@router.get("/ping")
async def ping():
    """
    서버가 정상적으로 실행 중인지 확인하기 위한 가장 간단한 엔드포인트입니다.
    "pong" 응답을 반환하면 서버가 요청을 받을 수 있는 상태임을 의미합니다.
    로드 밸런서나 간단한 모니터링 시스템에서 서비스의 가용성을 확인할 때 유용합니다.
    """
    return {"status": "ok", "message": "pong"}


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    서비스의 주요 의존성(데이터베이스, 벡터 스토어)들의 상태를 종합적으로 점검하는
    상세 헬스체크 엔드포인트입니다.

    - **데이터베이스**: `engine.connect()`를 통해 실제 연결을 시도하여 상태를 확인합니다.
    - **Milvus**: `MilvusVectorStore.health_check()`를 통해 연결 및 서버 상태를 확인합니다.

    모든 의존성이 정상일 때만 최상위 상태가 'ok'가 되므로,
    시스템 전체의 건강 상태를 파악하는 데 사용됩니다.

    Args:
        db (Session): FastAPI 의존성 주입을 통해 얻은 데이터베이스 세션.

    Returns:
        dict: 각 서비스의 상세 상태 정보를 담은 딕셔너리.
    """
    # 데이터베이스 연결 상태 확인
    db_ok = False
    try:
        # DB 세션을 사용하여 간단한 쿼리를 실행, 연결 유효성 검사
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.error(f"데이터베이스 헬스체크 실패: {e}")

    # Milvus 벡터 스토어 연결 상태 확인
    milvus_ok = False
    try:
        vector_store = MilvusVectorStore()
        milvus_ok = vector_store.health_check()
    except Exception as e:
        logger.warning(f"Milvus 헬스체크 실패: {e}")

    # 모든 서비스가 정상일 때만 200 OK 응답, 그렇지 않으면 503 Service Unavailable
    if db_ok and milvus_ok:
        return {
            "status": "ok",
            "services": {
                "database": "ok",
                "milvus": "ok"
            }
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "error",
                "services": {
                    "database": "ok" if db_ok else "error",
                    "milvus": "ok" if milvus_ok else "error"
                }
            }
        )
