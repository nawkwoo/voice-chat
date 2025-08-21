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

logger = get_logger("voice_chat")

# --- APIRouter 생성 ---
# "/api" 접두사와 "voice_chat" 태그를 사용하여 라우터를 생성합니다.
# 이 라우터는 음성 채팅의 핵심 로직을 처리하는 엔드포인트를 담당합니다.
router = APIRouter(prefix="/api", tags=["voice_chat"])


@router.post("/voice-chat")
async def voice_chat(
    file: UploadFile = File(...),
    user_id: str = None,
    session_id: str = None,
    db: Session = Depends(get_db)
):
    """
    사용자의 음성 입력을 받아 STT, LLM, TTS를 순차적으로 처리하여
    음성 응답을 생성하는 메인 파이프라인입니다.
    
    1.  **STT (Speech-to-Text)**: 사용자의 음성 파일(.wav, .mp3, .webm)을 텍스트로 변환합니다.
    2.  **LLM (Large Language Model)**:
        - `user_id`와 `session_id`가 제공되면, 이전 대화 내용을 컨텍스트로 활용합니다.
        - STT 변환 결과를 바탕으로 적절한 답변을 생성합니다.
        - 대화 내용을 데이터베이스와 벡터 스토어에 저장하여 다음 대화에 활용합니다.
    3.  **TTS (Text-to-Speech)**: LLM이 생성한 텍스트 답변을 음성으로 변환합니다.
    
    Args:
        file (UploadFile): 사용자의 음성 파일
        user_id (str, optional): 사용자 ID. 컨텍스트 유지를 위해 필요.
        session_id (str, optional): 대화 세션 ID. 컨텍스트 유지를 위해 필요.
        db (Session): 데이터베이스 세션
        
    Returns:
        StreamingResponse: 생성된 음성 응답(audio/wav)과 처리 시간 정보를 담은 헤더
    """
    start_time = time.time()
    
    try:
        # --- 1. 입력 파일 검증 및 읽기 ---
        if not file.filename or not file.filename.lower().endswith(('.wav', '.mp3', '.webm')):
            raise HTTPException(status_code=400, detail="지원하지 않는 오디오 파일 형식입니다. (.wav, .mp3, .webm 지원)")
        
        audio_data = await file.read()
        if not audio_data:
            raise HTTPException(status_code=400, detail="오디오 파일이 비어 있습니다.")
        
        # --- 2. STT (Speech-to-Text) 처리 ---
        stt_start = time.time()
        text = transcribe(audio_data)
        stt_time = (time.time() - stt_start) * 1000
        
        if not text or not text.strip():
            logger.warning("STT 결과가 비어있습니다. 음성 인식이 되지 않았을 수 있습니다.")
            raise HTTPException(status_code=400, detail="음성을 텍스트로 변환할 수 없습니다. 명확하게 다시 말씀해주세요.")
        
        logger.info(f"STT 변환 결과 ({stt_time:.0f}ms): {text}")
        
        # --- 3. LLM 응답 생성 (컨텍스트 기반) ---
        llm_response = ""
        llm_time = 0
        
        # user_id와 session_id가 제공된 경우에만 LLM 컨텍스트 처리 수행
        if user_id and session_id:
            try:
                # 대화 컨텍스트 조회
                # 현재 사용자 발화와 관련된 이전 대화 내용을 벡터 검색을 통해 가져옵니다.
                context = get_context_for_llm(user_id, session_id, text)
                
                # LLM에 전달할 프롬프트 구성
                prompt = f"이전 대화 맥락: {context}\n\n사용자 질문: {text}\n\n위 맥락을 바탕으로 사용자 질문에 간결하게 답변해줘."
                
                # LLM 응답 생성
                llm_start = time.time()
                llm_response = generate_response(prompt)
                llm_time = (time.time() - llm_start) * 1000
                logger.info(f"LLM 응답 생성 ({llm_time:.0f}ms): {llm_response}")
                
                # 대화 기록 저장 (사용자 발화와 AI 응답 모두)
                # 성능 측정을 위해 각 단계의 처리 시간도 함께 기록합니다.
                add_message_with_vector(db, session_id, user_id, "user", text, int(stt_time))
                if llm_response:
                    add_message_with_vector(db, session_id, user_id, "assistant", llm_response, int(llm_time))
                
            except Exception as e:
                logger.error(f"LLM 처리 중 오류 발생: {e}")
                llm_response = "죄송합니다. 답변을 생성하는 중에 문제가 발생했습니다."
        
        # --- 4. TTS (Text-to-Speech) 처리 ---
        tts_start = time.time()
        # LLM 응답이 있으면 그 내용을, 없으면 간단한 확인 메시지를 음성으로 변환
        response_text = llm_response if llm_response else "음성을 성공적으로 인식했습니다."
        audio_response = text_to_speech(response_text)
        tts_time = (time.time() - tts_start) * 1000
        
        # --- 5. 최종 응답 생성 및 로깅 ---
        total_time = (time.time() - start_time) * 1000
        
        logger.info(f"음성 채팅 처리 완료: STT={stt_time:.0f}ms, LLM={llm_time:.0f}ms, TTS={tts_time:.0f}ms, 총 소요시간={total_time:.0f}ms")
        
        # StreamingResponse를 사용하여 생성된 오디오를 클라이언트에 전송
        # HTTP 헤더에 각 단계별 처리 시간 정보를 포함하여 성능 분석에 활용
        return StreamingResponse(
            io.BytesIO(audio_response),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=response.wav",
                "X-Processing-Time": f"{total_time:.0f}",
                "X-STT-Time": f"{stt_time:.0f}",
                "X-LLM-Time": f"{llm_time:.0f}",
                "X-TTS-Time": f"{tts_time:.0f}",
                "X-User-Input": text.encode('utf-8'), # 어떤 텍스트로 인식되었는지 확인용
                "X-AI-Response": llm_response.encode('utf-8') # AI가 어떤 답변을 생성했는지 확인용
            }
        )
        
    except HTTPException:
        # 핸들링된 HTTP 예외는 그대로 전달
        raise
    except Exception as e:
        logger.error(f"음성 채팅 파이프라인에서 예기치 않은 오류 발생: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="음성 채팅 처리 중 서버 내부 오류가 발생했습니다.")
