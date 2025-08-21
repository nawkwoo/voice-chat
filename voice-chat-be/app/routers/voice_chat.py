"""
음성 채팅 라우터
"""

import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.deps import get_db
from app.services.stt import transcribe
from app.services.llm import generate_response
from app.services.tts import text_to_speech
from app.services.conversation import get_conversation_service, add_message_with_vector, get_context_for_llm
from app.utils.logging import get_logger
import io

import os
import tempfile

from app.database.models import ConversationSession
from app.services.conversation_service import get_conversation_service, ConversationService

logger = get_logger("voice_chat")

# --- APIRouter 생성 ---
# WebSocket 엔드포인트는 main.py에서 직접 처리하므로,
# 이 라우터는 향후 음성 채팅과 관련된 일반 HTTP 엔드포인트를 위해 유지됩니다.
router = APIRouter()


# 현재 핵심 음성 채팅 로직은 main.py의 WebSocket 엔드포인트로 이전되었습니다.
# 이 HTTP 엔드포인트는 테스트, 단일 파일 처리 또는 비실시간 처리를 위해
# 남겨두거나 필요에 따라 확장할 수 있습니다.
# 아래는 WebSocket 로직을 기반으로 재구성한 HTTP 엔드포인트의 예시입니다.

@router.post("/voice-chat/upload")
async def http_voice_chat(
    file: UploadFile = File(...),
    session_id: str = None,
    db_session: Session = Depends(get_db)
):
    """
    HTTP를 통해 업로드된 단일 음성 파일에 대해 STT-LLM-TTS 파이프라인을 실행합니다.

    이 엔드포인트는 실시간 스트리밍이 아닌, 전체 음성 파일이 업로드된 후
    전체 응답을 생성하여 반환하는 비실시간 처리에 적합합니다.

    Args:
        file (UploadFile): 사용자가 업로드한 음성 파일 (wav, mp3 등).
        session_id (str): 대화의 맥락을 이어가기 위한 세션 ID.
        db_session (Session): FastAPI 의존성 주입을 통해 제공되는 DB 세션.

    Returns:
        StreamingResponse: 생성된 음성 응답(audio/wav)을 스트리밍 형태로 반환합니다.
    """
    start_time = time.time()
    conversation_service = ConversationService(db_session)

    # 1. 세션 유효성 검사 또는 생성
    if not session_id:
        raise HTTPException(status_code=400, detail="세션 ID가 필요합니다.")

    session = db_session.query(ConversationSession).filter(ConversationSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"세션 '{session_id}'을 찾을 수 없습니다.")

    # 2. 오디오 데이터 처리 및 STT
    audio_data = await file.read()
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, file.filename)
    with open(temp_file_path, "wb") as f:
        f.write(audio_data)

    user_text = transcribe(temp_file_path)
    os.remove(temp_file_path)
    os.rmdir(temp_dir)

    if not user_text or not user_text.strip():
        raise HTTPException(status_code=400, detail="음성을 인식하지 못했습니다.")

    # 3. 사용자 메시지 저장
    conversation_service.add_message(session_id, "user", user_text)

    # 4. LLM 컨텍스트 생성 및 응답 얻기
    context = conversation_service.get_context_for_llm(session_id, user_text)
    prompt = f"### 이전 대화:\n{context}\n\n### 사용자 질문:\n{user_text}\n\n### 답변:"
    ai_response_text = generate_response(prompt)

    # 5. AI 응답 메시지 저장
    if ai_response_text:
        conversation_service.add_message(session_id, "assistant", ai_response_text)

    # 6. TTS로 음성 생성
    audio_response = text_to_speech(ai_response_text or "죄송합니다, 답변을 생성하지 못했습니다.")
    if not audio_response:
        raise HTTPException(status_code=500, detail="음성 응답을 생성하지 못했습니다.")

    total_time = (time.time() - start_time) * 1000
    logger.info(f"HTTP 음성 채팅 처리 완료. 총 소요시간={total_time:.0f}ms")

    return StreamingResponse(io.BytesIO(audio_response), media_type="audio/wav")
