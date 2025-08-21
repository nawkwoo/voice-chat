"""
데이터베이스 모델(테이블) 정의

이 모듈은 SQLAlchemy ORM(Object Relational Mapper)을 사용하여
애플리케이션에서 사용할 데이터베이스 테이블들을 파이썬 클래스로 정의합니다.
- 각 클래스는 데이터베이스의 테이블에 해당합니다.
- 클래스의 속성(attribute)은 테이블의 컬럼(column)에 해당합니다.
- `relationship`을 통해 테이블 간의 관계(FK)를 정의합니다.
"""

from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Boolean, ForeignKey, Float
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid

# 모든 모델 클래스가 상속받아야 할 기본(Base) 클래스를 생성합니다.
# SQLAlchemy는 이 Base 클래스를 통해 어떤 클래스들이 테이블과 매핑되는지 추적합니다.
Base = declarative_base()


class User(Base):
    """
    사용자 정보를 저장하는 'users' 테이블 모델입니다.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), unique=True, nullable=False, index=True,
                   comment="애플리케이션에서 사용하는 고유 사용자 ID")
    created_at = Column(DateTime, default=datetime.utcnow,
                        comment="사용자 레코드 생성 시각")
    last_active_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
                            comment="사용자 최근 활동 시각 (레코드 업데이트 시 자동 갱신)")

    # --- 관계 설정 (Relationship) ---
    # User와 ConversationSession 간의 일대다(One-to-Many) 관계를 정의합니다.
    # - `back_populates`: 양방향 관계를 설정하여 `ConversationSession.user`를 통해 User에 접근할 수 있게 합니다.
    # - `cascade`: User가 삭제될 때 관련된 모든 ConversationSession도 함께 삭제되도록 설정합니다.
    sessions = relationship("ConversationSession", back_populates="user", cascade="all, delete-orphan")


class ConversationSession(Base):
    """
    개별 대화 세션의 정보를 저장하는 'conversation_sessions' 테이블 모델입니다.
    하나의 세션은 여러 개의 메시지를 포함할 수 있습니다.
    """
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True,
                        comment="애플리케이션에서 사용하는 고유 세션 ID")
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, index=True,
                   comment="이 세션을 소유한 사용자의 ID (users.user_id 외래 키)")
    started_at = Column(DateTime, default=datetime.utcnow,
                        comment="세션 시작 시각")
    ended_at = Column(DateTime, nullable=True,
                      comment="세션 종료 시각 (진행 중인 세션은 NULL)")

    # --- 관계 설정 (Relationship) ---
    user = relationship("User", back_populates="sessions")
    messages = relationship("ConversationMessage", back_populates="session", cascade="all, delete-orphan")


class ConversationMessage(Base):
    """
    각각의 대화 메시지를 저장하는 'conversation_messages' 테이블 모델입니다.
    사용자 발화와 AI 응답 모두 이 테이블에 저장됩니다.
    """
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(100), unique=True, nullable=False, index=True,
                        comment="애플리케이션에서 사용하는 고유 메시지 ID")
    session_id = Column(String(100), ForeignKey("conversation_sessions.session_id"), nullable=False, index=True,
                        comment="이 메시지가 속한 세션의 ID (conversation_sessions.session_id 외래 키)")
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, index=True,
                   comment="메시지를 발생시킨 사용자의 ID (users.user_id 외래 키)")
    role = Column(String(20), nullable=False, index=True,
                  comment="메시지 발화자 역할 ('user' 또는 'assistant')")
    content = Column(Text, nullable=False,
                   comment="메시지의 실제 텍스트 내용")
    processing_time_ms = Column(Integer, nullable=True,
                                comment="이 메시지를 생성/처리하는 데 걸린 시간 (ms)")
    created_at = Column(DateTime, default=datetime.utcnow, index=True,
                        comment="메시지 생성 시각")

    # --- 관계 설정 (Relationship) ---
    session = relationship("ConversationSession", back_populates="messages")
