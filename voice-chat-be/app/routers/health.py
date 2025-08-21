"""
헬스체크 라우터
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.deps import get_db
from app.database.session import health_check as db_health_check
from app.utils.logging import get_logger

logger = get_logger("health")

# --- APIRouter 생성 ---
# "/api" 접두사와 "health" 태그를 사용하여 라우터를 생성합니다.
# 태그는 API 문서에서 엔드포인트들을 그룹화하는 데 사용됩니다.
router = APIRouter(prefix="/api", tags=["health"])


@router.get("/ping")
async def ping():
    """
    서버가 정상적으로 실행 중인지 확인하기 위한 간단한 Ping-Pong 엔드포인트입니다.
    로드 밸런서나 모니터링 시스템에서 서비스의 가용성을 확인할 때 유용합니다.
    """
    return {"status": "ok", "message": "pong"}


@router.get("/health")
async def health(db: Session = Depends(get_db)):
    """
    서비스의 주요 구성 요소(데이터베이스, 벡터 스토어 등)의 상태를 종합적으로 확인하는
    상세 헬스체크 엔드포인트입니다.
    
    - 데이터베이스: SQLAlchemy 세션을 통해 연결 상태를 확인합니다.
    - Milvus: Milvus 클라이언트를 통해 연결 및 서버 상태를 확인합니다.
    
    Args:
        db (Session): `get_db` 의존성 주입을 통해 얻은 데이터베이스 세션
    
    Returns:
        dict: 각 서비스의 상태 정보를 담은 딕셔너리
    """
    try:
        # 데이터베이스 연결 상태 확인
        db_status = "ok" if db_health_check() else "error"
        
        # Milvus 벡터 스토어 연결 상태 확인
        # Milvus는 선택적 구성 요소일 수 있으므로, 예외 처리를 통해
        # 연결 실패가 전체 헬스체크에 치명적인 영향을 주지 않도록 합니다.
        milvus_status = "unknown"
        try:
            from app.vector_store.milvus_client import MilvusVectorStore
            vector_store = MilvusVectorStore()
            milvus_status = "ok" if vector_store.health_check() else "error"
        except ImportError:
            logger.warning("MilvusVectorStore를 찾을 수 없어 Milvus 헬스체크를 건너뜁니다.")
            milvus_status = "not_configured"
        except Exception as e:
            logger.warning(f"Milvus 헬스체크 중 오류가 발생했습니다: {e}")
            milvus_status = "error"
        
        # 모든 서비스가 정상일 때만 최상위 status를 'ok'로 설정
        overall_status = "ok" if db_status == "ok" and milvus_status in ["ok", "not_configured"] else "error"
        
        return {
            "status": overall_status,
            "services": {
                "database": db_status,
                "milvus": milvus_status
            }
        }
        
    except Exception as e:
        logger.error(f"헬스체크 처리 중 심각한 오류가 발생했습니다: {e}")
        return {
            "status": "error",
            "services": {
                "database": "error",
                "milvus": "error"
            },
            "error": str(e)
        }
