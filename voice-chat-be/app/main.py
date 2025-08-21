"""
Voice Chat Backend - FastAPI 애플리케이션
"""

import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.settings import settings
from app.database.session import init_database
from app.utils.logging import setup_logging, get_logger
from app.ws.manager import manager, handle_websocket_message
from app.ws.manager import ConnectionManager

# 애플리케이션의 최상위 경로를 sys.path에 추가하여
# Docker 환경이나 다른 실행 환경에서 `RealTime_zeroshot_TTS_ko` 같은
# 프로젝트 레벨 모듈을 문제없이 임포트할 수 있도록 설정합니다.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


# .env 파일에서 로드된 Hugging Face 토큰을 os 환경 변수로 명시적으로 설정합니다.
# 이는 `transformers` 라이브러리가 내부적으로 환경 변수를 통해 인증을 처리하기 때문입니다.
if settings.HUGGING_FACE_HUB_TOKEN:
    os.environ["HUGGING_FACE_HUB_TOKEN"] = settings.HUGGING_FACE_HUB_TOKEN


# Loguru를 사용하여 애플리케이션 전역 로거를 설정합니다.
# 로그 레벨, 포맷 등을 중앙에서 관리합니다.
logger = setup_logging()

# WebSocket 연결을 관리하는 중앙 관리자 인스턴스입니다.
manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 애플리케이션의 시작과 종료 시점에 실행될 로직을 정의하는
    라이프사이클 이벤트 핸들러입니다.
    - 시작(startup): 데이터베이스 연결 및 테이블 생성 등의 초기화 작업을 수행합니다.
    - 종료(shutdown): 리소스 정리 등의 마무리 작업을 수행합니다.
    """
    # 애플리케이션 시작
    logger.info("🚀 Voice Chat Backend 애플리케이션을 시작합니다.")
    try:
        init_database()
        logger.info("✅ 데이터베이스가 성공적으로 초기화되었습니다.")
    except Exception as e:
        logger.critical(f"❌ 데이터베이스 초기화 실패, 애플리케이션을 시작할 수 없습니다: {e}")
        # DB 연결 실패는 심각한 문제이므로, 여기서 애플리케이션을 중단시킬 수 있습니다.
        # (예: raise SystemExit("Database connection failed"))

    yield

    # 애플리케이션 종료
    logger.info("🛑 Voice Chat Backend 애플리케이션을 종료합니다.")


# FastAPI 애플리케이션 인스턴스를 생성하고, lifespan 이벤트를 등록합니다.
app = FastAPI(
    title="Voice Chat AI Backend",
    description="실시간 음성 기반 AI 채팅 서비스의 백엔드 시스템입니다.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS (Cross-Origin Resource Sharing) 미들웨어를 설정합니다.
# 웹 브라우저에서 다른 도메인의 프론트엔드 애플리케이션이
# 이 API 서버와 통신할 수 있도록 허용합니다.
# 프로덕션 환경에서는 보안을 위해 `allow_origins`를 특정 도메인으로 제한해야 합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 오리진 허용 (프로덕션 환경에서는 특정 도메인만 허용하는 것이 좋습니다)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

logger.info("🤖 AI 모델은 필요 시점에 동적으로 로드됩니다 (지연 로딩).")

# --- WebSocket 엔드포인트 ---
# 실시간 양방향 통신을 위한 주 엔드포인트입니다.
@app.websocket("/ws/voice/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    클라이언트와 실시간 음성 채팅을 수행하는 WebSocket 엔드포인트입니다.

    - 경로 파라미터 `session_id`를 통해 특정 대화 세션을 식별합니다.
    - 연결이 수립되면 `manager`가 연결을 등록하고 관리합니다.
    - 클라이언트로부터 오디오 데이터가 포함된 JSON 메시지를 수신하면,
      STT -> LLM -> TTS 파이프라인을 거쳐 음성 응답을 다시 클라이언트로 전송합니다.
    - 연결이 끊어지면 `manager`가 연결을 해제하고 관련 리소스를 정리합니다.
    """
    # user_id는 향후 인증 시스템이 도입되면 토큰 등에서 추출하도록 수정할 수 있습니다.
    # 현재는 임시로 세션 ID를 기반으로 생성합니다.
    user_id = f"user_{session_id}"
    await manager.connect(websocket, user_id, session_id)
    try:
        while True:
            # 클라이언트로부터 텍스트(JSON) 형태의 메시지를 기다립니다.
            data = await websocket.receive_text()
            # 수신된 메시지를 비동기적으로 처리합니다.
            await manager.handle_message(websocket, user_id, session_id, data)
    except WebSocketDisconnect:
        # 클라이언트 연결이 정상적으로 또는 비정상적으로 끊겼을 때 처리합니다.
        manager.disconnect(websocket)
        logger.info(f"WebSocket 연결이 종료되었습니다: {user_id} (세션: {session_id})")


# --- 라우터 등록 ---
# 각 기능별로 분리된 API 라우터들을 메인 애플리케이션에 포함시킵니다.
# 이를 통해 엔드포인트 관리가 용이해지고 코드의 모듈성이 향상됩니다.
from app.routers import health, sessions

app.include_router(health.router, prefix="/api", tags=["System"])
app.include_router(sessions.router, prefix="/api", tags=["Session Management"])


if __name__ == "__main__":
    import uvicorn
    
    # --- SSL/TLS 설정 ---
    # 환경 변수에 SSL 인증서와 키 파일 경로가 설정되어 있는지 확인하고,
    # 존재할 경우 HTTPS로 서버를 실행합니다.
    ssl_config = {}
    if settings.SSL_CRT_FILE and settings.SSL_KEY_FILE:
        if os.path.exists(settings.SSL_CRT_FILE) and os.path.exists(settings.SSL_KEY_FILE):
            ssl_config = {
                "ssl_certfile": settings.SSL_CRT_FILE,
                "ssl_keyfile": settings.SSL_KEY_FILE
            }
            logger.info("🔒 HTTPS (SSL/TLS) 모드로 서버를 실행합니다.")
        else:
            logger.warning("⚠️ SSL 인증서 파일을 찾을 수 없습니다. HTTP 모드로 실행합니다.")
    else:
        logger.info("🌐 HTTP 모드로 서버를 실행합니다.")
    
    # --- Uvicorn 서버 실행 ---
    # FastAPI 애플리케이션을 Uvicorn ASGI 서버를 통해 실행합니다.
    # reload=True 옵션은 코드 변경 시 서버를 자동으로 재시작하여 개발 편의성을 높입니다.
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        **ssl_config
    )
