import logging
import sys
from typing import Optional
from app.settings import settings


def setup_logging(
    level: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """로깅 설정을 초기화하고 로거를 반환합니다."""
    
    # 기본 설정
    log_level = level or settings.LOG_LEVEL
    log_format = format_string or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 로거 생성
    logger = logging.getLogger("voice_chat")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 이미 핸들러가 설정되어 있으면 추가하지 않음
    if logger.handlers:
        return logger
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # 포맷터
    formatter = logging.Formatter(log_format)
    console_handler.setFormatter(formatter)
    
    # 핸들러 추가
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """지정된 이름의 로거를 반환합니다."""
    return logging.getLogger(f"voice_chat.{name}")


# 기본 로거 설정
logger = setup_logging()
