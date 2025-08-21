"""
데이터베이스 모델 정의
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    """
    사용자 정보를 저장하는 테이블 모델 (ORM).
    
    Attributes:
        id (int): 고유 식별자 (Auto Increment Primary Key).
        user_id (str): 애플리케이션에서 사용하는 고유한 사용자 ID.
        created_at (datetime): 사용자 생성 시간.
        last_active_at (datetime): 마지막 활동 시간.
        sessions (relationship): 이 사용자에 속한 모든 대화 세션 목록 (역참조).
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), unique=True, nullable=False, index=True, comment="애플리케이션 레벨에서 사용하는 고유 사용자 ID")
    created_at = Column(DateTime, default=datetime.utcnow, comment="사용자 레코드 생성 시간")
    last_active_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="사용자 최근 활동 시간 (업데이트 시 자동 갱신)")
    
    # --- 관계 설정 ---
    # User가 삭제될 때 관련된 ConversationSession도 모두 삭제되도록 cascade 옵션 설정.
    sessions = relationship("ConversationSession", back_populates="user", cascade="all, delete-orphan")


class ConversationSession(Base):
    """
    개별 대화 세션 정보를 저장하는 테이블 모델.
    하나의 세션은 여러 개의 메시지를 포함할 수 있습니다.
    
    Attributes:
        id (int): 고유 식별자 (PK).
        session_id (str): 애플리케이션에서 사용하는 고유한 세션 ID.
        user_id (str): 이 세션을 소유한 사용자의 ID (FK).
        started_at (datetime): 세션 시작 시간.
        ended_at (datetime): 세션 종료 시간 (null일 경우 진행 중).
        total_messages (int): 세션에 포함된 총 메시지 수 (캐시/집계용).
        user (relationship): 이 세션을 소유한 User 객체 (역참조).
        messages (relationship): 이 세션에 속한 모든 메시지 목록 (역참조).
    """
    __tablename__ = "conversation_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True, comment="애플리케이션 레벨에서 사용하는 고유 세션 ID")
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, index=True, comment="users.user_id 외래 키")
    started_at = Column(DateTime, default=datetime.utcnow, comment="세션 시작 시간")
    ended_at = Column(DateTime, nullable=True, comment="세션 종료 시간")
    total_messages = Column(Integer, default=0, comment="세션 내 총 메시지 수")
    
    # --- 관계 설정 ---
    # `back_populates`는 양방향 관계를 설정하여 각 모델에서 서로를 참조할 수 있게 합니다.
    user = relationship("User", back_populates="sessions")
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")


class ConversationMessage(Base):
    """
    개별 대화 메시지를 저장하는 테이블 모델.
    사용자 발화와 시스템 응답 모두 이 테이블에 저장됩니다.
    
    Attributes:
        id (int): 고유 식별자 (PK).
        message_id (str): 애플리케이션에서 사용하는 고유한 메시지 ID.
        session_id (str): 이 메시지가 속한 세션의 ID (FK).
        user_id (str): 이 메시지를 발생시킨 사용자의 ID (FK).
        role (str): 메시지 발화자 역할 ('user' 또는 'assistant').
        content (str): 메시지의 텍스트 내용.
        milvus_vector_id (str): Milvus 벡터 스토어에 저장된 경우의 벡터 ID.
        processing_time_ms (int): 이 메시지를 처리하는 데 걸린 시간 (ms).
        created_at (datetime): 메시지 생성 시간.
        session (relationship): 이 메시지가 속한 ConversationSession 객체 (역참조).
    """
    __tablename__ = "conversation_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(100), unique=True, nullable=False, index=True, comment="애플리케이션 레벨에서 사용하는 고유 메시지 ID")
    session_id = Column(String(100), ForeignKey("conversation_sessions.session_id"), nullable=False, index=True, comment="conversation_sessions.session_id 외래 키")
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, index=True, comment="users.user_id 외래 키")
    role = Column(String(20), nullable=False, index=True, comment="메시지 발화자 역할 ('user' 또는 'assistant')")
    content = Column(Text, nullable=False, comment="메시지 본문")
    milvus_vector_id = Column(String(100), nullable=True, index=True, comment="Milvus에 저장된 경우의 벡터 ID")
    processing_time_ms = Column(Integer, nullable=True, comment="메시지 처리 소요 시간(ms)")
    created_at = Column(DateTime, default=datetime.utcnow, index=True, comment="메시지 생성 시간")
    
    # --- 관계 설정 ---
    session = relationship("ConversationSession", back_populates="messages")
