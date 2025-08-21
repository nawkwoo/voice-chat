import os
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    애플리케이션의 모든 설정을 관리하는 Pydantic 모델 클래스입니다.

    `pydantic-settings` 라이브러리를 사용하여 .env 파일, 환경 변수 등에서
    설정 값을 자동으로 로드하고 타입 검증을 수행합니다.
    이 중앙화된 접근 방식을 통해 설정 관리가 용이해집니다.

    - 우선순위: 환경 변수 > .env 파일 > 모델에 정의된 기본값
    """

    # --- Pydantic 설정 ---
    # `model_config`은 Pydantic 모델의 동작을 제어합니다.
    # - env_file: 읽어올 .env 파일의 이름을 지정합니다.
    # - extra='ignore': .env 파일이나 환경 변수에 모델에 정의되지 않은 필드가 있어도 무시합니다.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')

    # --- 일반 설정 ---
    ENVIRONMENT: str = "local"
    """애플리케이션이 실행되는 환경 (예: 'local', 'development', 'production')"""
    LOG_LEVEL: str = "INFO"
    """애플리케이션의 로깅 레벨 (예: 'DEBUG', 'INFO', 'WARNING', 'ERROR')"""

    # --- 데이터베이스 설정 (MariaDB) ---
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "voice_chat_user"
    DB_PASSWORD: str = "voicechat2024"
    DB_NAME: str = "voice_chat_db"
    DB_ROOT_PASSWORD: str = "voicechat2024" # docker-compose에서 DB 초기화 시 사용

    # --- 벡터 스토어 설정 (Milvus) ---
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "voice_conversations"
    """Milvus 내에서 사용할 컬렉션(테이블과 유사)의 이름"""

    # --- AI 모델 및 Hugging Face 설정 ---
    HUGGING_FACE_HUB_TOKEN: Optional[str] = None
    """Hugging Face Hub에서 private 또는 gated 모델(예: Gemma)을 다운로드하기 위한 API 토큰"""
    HF_HOME: str = "/root/.cache/huggingface"
    """Hugging Face 모델과 데이터셋이 캐시될 디렉토리 경로"""

    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    """Milvus에 텍스트를 벡터로 변환하여 저장할 때 사용할 임베딩 모델의 ID"""
    LLM_MODEL: str = "google/gemma-2-2b-it"
    """텍스트 응답 생성을 위해 사용할 대규모 언어 모델(LLM)의 ID"""
    WHISPER_MODEL: str = "small"
    """음성-텍스트 변환(STT)에 사용할 Whisper 모델의 크기 (tiny, base, small, medium, large)"""

    # --- 기능 활성화 토글 ---
    # 이 플래그들을 사용하여 특정 AI 기능의 활성화/비활성화 여부를 제어할 수 있습니다.
    # 개발 또는 리소스 제약 환경에서 특정 모델을 로드하지 않도록 할 때 유용합니다.
    STT_ENABLED: bool = True
    LLM_ENABLED: bool = True
    TTS_ENABLED: bool = True

    # --- TTS(Text-to-Speech) 설정 ---
    TTS_REF_SPEAKER: str = "ttsmaker-file-2025-7-23-12-56-21.mp3"
    """TTS 음성 생성을 위해 참조할 목소리(화자)의 오디오 파일 경로"""

    # --- SSL/TLS 설정 (HTTPS) ---
    SSL_CRT_FILE: Optional[str] = None
    """SSL 인증서 파일(.pem, .crt)의 경로"""
    SSL_KEY_FILE: Optional[str] = None
    """SSL 개인 키 파일(.key)의 경로"""


# --- 전역 설정 인스턴스 ---
# 애플리케이션 전체에서 `settings` 객체를 통해 설정 값에 접근할 수 있도록
# 단일 인스턴스를 생성하고 초기화합니다.
@lru_cache
def get_settings() -> Settings:
    """
    설정 객체를 반환합니다. lru_cache를 사용하여 최초 호출 시 한 번만 Settings 객체를 생성하고
    이후에는 캐시된 객체를 반환하여 성능을 최적화합니다.
    """
    return Settings()

settings = get_settings()
