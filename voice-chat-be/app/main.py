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

# --- 경로 설정 ---
# 현재 파일(main.py)의 상위 디렉토리(app)의 상위 디렉토리(voice-chat-be)를
# 파이썬 모듈 검색 경로에 추가합니다.
# 이렇게 하면 `RealTime_zeroshot_TTS_ko`와 같은 프로젝트 루트의 다른 모듈을
# 절대 경로로 임포트할 수 있게 됩니다.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# --- 환경 변수 설정 ---
# .env 파일에서 로드된 Hugging Face 토큰을 os 환경 변수로 명시적으로 설정합니다.
# 이렇게 하면 transformers 라이브러리가 gated model에 접근할 때 토큰을 확실히 찾을 수 있습니다.
if settings.HUGGING_FACE_HUB_TOKEN:
    os.environ["HUGGING_FACE_HUB_TOKEN"] = settings.HUGGING_FACE_HUB_TOKEN

# --- 로깅 설정 ---
# 애플리케이션 전반에 사용될 로거를 설정합니다.
# `setup_logging` 함수는 로그 포맷, 레벨, 핸들러 등을 구성합니다.
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션의 시작과 종료 시 수행될 작업을 정의하는 Lifespan 컨텍스트 매니저입니다.
    - 시작 시: 데이터베이스 연결, 모델 로딩 등 초기화 작업을 수행합니다.
    - 종료 시: 리소스 정리 등 마무리 작업을 수행합니다.
    """
    # 애플리케이션 시작 시 수행될 작업
    logger.info("🚀 Voice Chat Backend 애플리케이션을 시작합니다.")
    
    try:
        # 데이터베이스 연결 및 테이블 생성
        init_database()
        logger.info("✅ 데이터베이스가 성공적으로 초기화되었습니다.")
    except Exception as e:
        logger.error(f"❌ 데이터베이스 초기화 중 오류가 발생했습니다: {e}")
    
    yield
    
    # 애플리케이션 종료 시 수행될 작업
    logger.info("🛑 Voice Chat Backend 애플리케이션을 종료합니다.")


# --- FastAPI 애플리케이션 생성 ---
# FastAPI 인스턴스를 생성하고 기본 정보를 설정합니다.
# lifespan 이벤트를 등록하여 애플리케이션 시작/종료 시점을 관리합니다.
app = FastAPI(
    title="실시간 음성 대화 서비스",
    description="MariaDB와 Milvus를 사용하여 세션별로 독립된 컨텍스트를 제공하는 음성 챗봇입니다.",
    version="2.1.0",
    lifespan=lifespan
)

# --- 미들웨어 설정 ---
# CORS (Cross-Origin Resource Sharing) 미들웨어를 추가하여
# 다른 도메인에서의 요청을 허용합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 오리진 허용 (프로덕션 환경에서는 특정 도메인만 허용하는 것이 좋습니다)
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메소드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

logger.info("🤖 AI 모델은 필요 시점에 동적으로 로드됩니다 (지연 로딩).")

# --- 라우터 등록 ---
# 각 기능별로 분리된 라우터들을 애플리케이션에 등록합니다.
# 이를 통해 코드의 모듈성을 높이고 관리가 용이해집니다.
from app.routers import health, sessions, tts_api, voice_chat

app.include_router(health.router)       # 상태 체크 API
app.include_router(sessions.router)     # 대화 세션 관리 API
app.include_router(tts_api.router)      # TTS(Text-to-Speech) API
app.include_router(voice_chat.router)   # 음성 채팅 관련 API

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
):
    """
    실시간 양방향 통신을 위한 WebSocket 엔드포인트입니다.
    
    - 클라이언트 연결 시: `manager.connect`를 호출하여 연결을 등록합니다.
    - 메시지 수신 시: `handle_websocket_message`를 통해 메시지를 처리합니다.
    - 연결 종료 시: `manager.disconnect`를 호출하여 연결을 해제합니다.
    
    Args:
        websocket (WebSocket): 현재 연결된 WebSocket 객체
        user_id (str): 클라이언트를 식별하는 사용자 ID
        session_id (str): 현재 대화 세션의 ID
    """
    connection_info = await manager.connect(websocket, user_id, session_id)
    
    try:
        # 클라이언트로부터 메시지를 무한정 대기하고 처리합니다.
        while True:
            logger.info(f"[세션 {session_id}] 클라이언트로부터 메시지를 기다립니다...")
            data = await websocket.receive_text()
            await handle_websocket_message(websocket, user_id, session_id, data)
            
    except WebSocketDisconnect:
        # 클라이언트 연결이 끊어졌을 때 처리
        logger.info(f"[WebSocket] 사용자 {user_id}의 연결이 종료되었습니다.")
        manager.disconnect(websocket)
    except Exception as e:
        # 그 외 예외 발생 시 처리
        logger.error(f"[WebSocket] 처리 중 오류 발생: {e}")
        manager.disconnect(websocket)


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
