"""
TTS API 라우터
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.tts import text_to_speech
from app.utils.logging import get_logger
import io

logger = get_logger("tts_api")

# --- APIRouter 생성 ---
# "/api/tts" 접두사와 "tts" 태그를 사용하여 라우터를 생성합니다.
# 이 라우터는 Text-to-Speech(TTS) 기능과 관련된 API 엔드포인트를 담당합니다.
router = APIRouter(prefix="/api/tts", tags=["tts"])


# --- 요청 모델 정의 ---
class TTSRequest(BaseModel):
    """
    TTS 변환을 요청할 때 사용되는 데이터 모델입니다.
    - text: 음성으로 변환할 텍스트
    """
    text: str


@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """
    입력된 텍스트를 음성 오디오 데이터로 변환하여 스트리밍 형태로 반환합니다.
    
    - 입력: JSON 형식의 텍스트 데이터 (`TTSRequest` 모델)
    - 처리: `text_to_speech` 서비스 함수를 호출하여 TTS 변환 수행
    - 출력: `audio/wav` 형식의 스트리밍 응답
    
    Args:
        request (TTSRequest): 음성으로 변환할 텍스트를 담은 요청 객체
        
    Returns:
        StreamingResponse: 생성된 오디오 데이터를 스트리밍으로 전송
    """
    try:
        # 입력 텍스트 유효성 검사
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="음성으로 변환할 텍스트가 비어 있습니다.")
        
        logger.info(f"TTS 변환 요청 수신: '{request.text[:30]}...'")
        
        # TTS 서비스 호출하여 텍스트를 음성 데이터(bytes)로 변환
        audio_data = text_to_speech(request.text)
        
        if not audio_data:
            logger.error("TTS 서비스에서 오디오 데이터를 생성하지 못했습니다.")
            raise HTTPException(status_code=500, detail="음성 데이터 생성에 실패했습니다.")
        
        logger.info(f"TTS 변환 완료, 오디오 데이터 크기: {len(audio_data)} bytes")
        
        # 생성된 오디오 데이터를 클라이언트에 스트리밍으로 전송
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=speech.wav"}
        )
        
    except HTTPException as http_exc:
        # HTTP 예외는 그대로 다시 발생시킴
        raise http_exc
    except Exception as e:
        logger.error(f"TTS 변환 과정에서 예기치 않은 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="서버 내부 오류가 발생했습니다.")
