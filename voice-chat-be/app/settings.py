import os
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # pydantic-settings가 .env 파일을 읽도록 설정
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='ignore')
    
    # 환경 설정
    ENVIRONMENT: str = "local"
    
    # 데이터베이스 설정
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "voice_chat_user"
    DB_PASSWORD: str = "voicechat2024"
    DB_NAME: str = "voice_chat_db"
    DB_ROOT_PASSWORD: str = "voicechat2024"
    
    # Milvus 설정
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "voice_conversations"
    
    # Hugging Face Hub
    HUGGING_FACE_HUB_TOKEN: Optional[str] = None

    # 모델 설정
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    LLM_MODEL: str = "google/gemma-2-2b-it"
    
    # 기능 토글
    LLM_ENABLED: bool = True
    TTS_ENABLED: bool = True
    
    # 로깅 설정
    LOG_LEVEL: str = "INFO"
    
    # Hugging Face 설정
    HF_HOME: str = "/root/.cache/huggingface"
    
    # SSL 설정
    SSL_CRT_FILE: Optional[str] = None
    SSL_KEY_FILE: Optional[str] = None
    
    # Whisper 설정
    WHISPER_MODEL: str = "small"
    
    # TTS 설정
    TTS_REF_SPEAKER: str = "ttsmaker-file-2025-7-23-12-56-21.mp3"


# 전역 설정 인스턴스
settings = Settings()
