"""
데이터베이스 세션 관리
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from app.settings import settings
from app.utils.logging import get_logger
from typing import Generator

logger = get_logger("database")


def create_database_engine():
    """
    환경 변수(`settings`)에 정의된 정보를 바탕으로 SQLAlchemy 데이터베이스 엔진을 생성합니다.
    - **Connection Pool**: `QueuePool`을 사용하여 데이터베이스 연결을 미리 생성하고 관리함으로써
      연결 생성/해제에 드는 비용을 줄이고 성능을 향상시킵니다.
    - **pool_pre_ping**: 세션을 가져오기 전에 간단한 쿼리를 실행하여 연결이 유효한지 확인합니다.
    - **pool_recycle**: 설정된 시간(초)이 지난 연결을 자동으로 재생성하여 연결 끊김 문제를 방지합니다.
    - **echo**: `development` 환경일 때 실행되는 SQL 쿼리를 로깅하여 디버깅을 돕습니다.
    
    Returns:
        SQLAlchemy Engine: 생성된 데이터베이스 엔진 객체
    """
    database_url = (
        f"mysql+pymysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}"
        f"/{settings.DB_NAME}?charset=utf8mb4"
    )
    
    engine = create_engine(
        database_url,
        poolclass=QueuePool,     # 요청을 대기열에 넣어 순차적으로 처리하는 커넥션 풀
        pool_size=10,            # 풀에서 유지할 최소 연결 수
        max_overflow=20,         # 풀 크기를 초과하여 생성할 수 있는 임시 연결 수
        pool_pre_ping=True,      # 세션 사용 전 연결 유효성 검사(ping) 활성화
        pool_recycle=3600,       # 1시간(3600초)마다 연결을 재생성하여 타임아웃 방지
        echo=settings.ENVIRONMENT == "development" # 개발 환경에서만 SQL 쿼리 로깅
    )
    
    logger.info(f"✅ 데이터베이스 엔진이 성공적으로 생성되었습니다 (Host: {settings.DB_HOST}:{settings.DB_PORT})")
    return engine


# --- 전역 엔진 및 세션 팩토리 ---
# 애플리케이션 전체에서 공유할 단일 데이터베이스 엔진을 생성합니다.
engine = create_database_engine()
# `sessionmaker`는 새로운 데이터베이스 세션 객체를 생성하는 팩토리 역할을 합니다.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI의 의존성 주입(Dependency Injection) 시스템을 위한 데이터베이스 세션 생성기입니다.
    - API 요청이 들어올 때마다 새로운 세션을 생성합니다.
    - 요청 처리가 끝나면(성공/실패 무관) `finally` 블록에서 세션을 항상 닫아 리소스를 해제합니다.
    
    Yields:
        Session: 생성된 SQLAlchemy 세션 객체
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """
    데이터베이스를 초기화합니다.
    `models.py`에 정의된 모든 SQLAlchemy 모델(테이블)을 데이터베이스에 생성합니다.
    애플리케이션 시작 시 호출됩니다.
    """
    try:
        # `models` 모듈을 임포트하여 Base에 메타데이터가 등록되도록 합니다.
        from app.database.models import Base
        
        # `Base.metadata.create_all`은 정의된 모든 테이블을 생성합니다 (이미 존재하면 건너뜀).
        Base.metadata.create_all(bind=engine)
        logger.info("✅ 데이터베이스 테이블이 성공적으로 초기화(생성)되었습니다.")
        
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 중 오류가 발생했습니다: {e}", exc_info=True)
        raise


def health_check() -> bool:
    """
    데이터베이스 연결 상태를 확인하는 헬스체크 함수입니다.
    간단한 쿼리(`SELECT 1`)를 실행하여 연결이 정상적인지 검사합니다.
    
    Returns:
        bool: 연결이 정상이면 True, 실패하면 False.
    """
    try:
        # 커넥션 풀에서 연결을 하나 가져와 테스트 쿼리를 실행합니다.
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"❌ 데이터베이스 헬스체크 실패: {e}")
        return False
