"""
STT (Speech-to-Text) 서비스
"""

import os
import time
import numpy as np
from typing import Union, Optional
import whisper
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger("stt")

# --- 전역 모델 캐시 ---
# Whisper 모델을 메모리에 한 번만 로드하여 재사용하기 위한 전역 변수입니다.
# API 요청 시마다 모델을 새로 로드하는 오버헤드를 방지합니다.
_whisper_model: Optional[whisper.Whisper] = None


def get_whisper_model(model_name: Optional[str] = None) -> whisper.Whisper:
    """
    OpenAI Whisper 모델을 지연 로드(lazy loading)합니다.
    - 모델이 아직 로드되지 않은 경우(`_whisper_model` is None), `whisper.load_model`을 호출하여
      모델을 로드하고 전역 변수 `_whisper_model`에 캐시합니다.
    - 이미 로드된 경우, 캐시된 모델 객체를 즉시 반환합니다.
    
    Args:
        model_name (str, optional): 로드할 Whisper 모델의 이름 (예: 'base', 'small', 'medium').
                                    기본값은 설정 파일(`settings.WHISPER_MODEL`)을 따릅니다.
                                    
    Returns:
        whisper.Whisper: 로드된 Whisper 모델 객체.
    """
    global _whisper_model
    
    if _whisper_model is None:
        model_name = model_name or settings.WHISPER_MODEL
        logger.info(f"🔄 Whisper STT 모델('{model_name}')의 지연 로딩을 시작합니다...")
        
        try:
            # `whisper.load_model`은 모델을 다운로드(필요 시)하고 메모리에 로드합니다.
            _whisper_model = whisper.load_model(model_name)
            logger.info(f"✅ Whisper STT 모델('{model_name}')이 성공적으로 로드되었습니다.")
        except Exception as e:
            logger.error(f"❌ Whisper STT 모델('{model_name}') 로딩 중 심각한 오류가 발생했습니다: {e}", exc_info=True)
            # 모델 로드 실패는 심각한 문제이므로 예외를 다시 발생시켜 상위 호출자에게 알립니다.
            raise
    
    return _whisper_model


def transcribe(
    audio_path: str,
    language: Optional[str] = 'ko'
) -> str:
    """
    주어진 오디오 파일 경로를 읽어 텍스트로 변환(transcribe)합니다.
    
    Args:
        audio_path (str): 변환할 오디오 파일의 경로.
        language (str, optional): 변환할 언어의 코드 (예: 'ko', 'en'). 기본값은 'ko'.
    
    Returns:
        str: 변환된 텍스트. 오류 발생 시 빈 문자열을 반환합니다.
    """
    start_time = time.time()
    
    try:
        # 모델을 가져오거나 로드합니다.
        model = get_whisper_model()
        
        if not os.path.exists(audio_path):
            logger.error(f"STT 변환을 위한 오디오 파일을 찾을 수 없습니다: {audio_path}")
            return ""

        result = model.transcribe(audio_path, language=language)
        transcribed_text = result["text"].strip()

        processing_time = (time.time() - start_time) * 1000
        logger.info(f"✅ STT 변환 완료 ({processing_time:.2f}ms). 결과: '{transcribed_text[:50]}...'")
        
        return transcribed_text
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        logger.error(f"❌ STT 변환 중 오류가 발생했습니다 ({processing_time:.2f}ms): {e}", exc_info=True)
        # STT 실패 시 빈 문자열을 반환합니다.
        return ""
