"""
FastAPI 의존성 주입
"""

from typing import Generator
from sqlalchemy.orm import Session
from app.database.session import get_db as get_db_session

# 데이터베이스 세션 의존성
def get_db() -> Generator[Session, None, None]:
    """데이터베이스 세션 의존성"""
    yield from get_db_session()
