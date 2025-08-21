"""
STT (Speech-to-Text) 서비스

이 모듈은 `openai-whisper` 라이브러리를 사용하여 오디오 데이터를 텍스트로 변환하는
STT(Speech-to-Text) 기능을 제공합니다.
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


def get_whisper_model(model_name: Optional[str] = None) -> Optional[whisper.Whisper]:
    """
    OpenAI Whisper 모델을 지연 로드(lazy loading)하고 전역적으로 캐싱합니다.

    이 함수는 실제 STT 기능이 처음 필요할 때 모델을 메모리에 로드하여
    애플리케이션의 초기 구동 시간을 단축하고 메모리 사용을 효율화합니다.
    한 번 로드된 모델은 전역 변수에 캐시되어 이후 요청에서는 즉시 반환됩니다.

    - `settings.STT_ENABLED`가 `False`이면 모델을 로드하지 않고 `None`을 반환합니다.

    Args:
        model_name (str, optional): 로드할 Whisper 모델의 이름 (예: 'base', 'small').
                                    제공되지 않으면 `settings.WHISPER_MODEL` 값을 사용합니다.

    Returns:
        Optional[whisper.Whisper]: 로드된 Whisper 모델 객체. 실패 또는 비활성화 시 None을 반환합니다.
    """
    global _whisper_model

    if not settings.STT_ENABLED:
        logger.info("STT 기능이 비활성화되어 있어 모델을 로드하지 않습니다.")
        return None

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
            raise e
    
    return _whisper_model


def transcribe(audio_path_or_data: Union[str, np.ndarray], language: Optional[str] = 'ko') -> str:
    """
    주어진 오디오 파일 경로 또는 NumPy 배열 데이터를 텍스트로 변환합니다.

    Args:
        audio_path_or_data (Union[str, np.ndarray]):
            변환할 오디오 파일의 경로(str) 또는 로드된 오디오 데이터(NumPy 배열).
        language (str, optional): 변환할 언어의 코드 (예: 'ko', 'en'). 기본값은 'ko'.

    Returns:
        str: 변환된 텍스트. 오류 발생 시 빈 문자열을 반환합니다.
    """
    start_time = time.time()

    try:
        # 모델을 가져오거나 로드합니다.
        model = get_whisper_model()
        if not model:
            logger.warning("STT 모델을 사용할 수 없어 변환을 건너뜁니다.")
            return ""

        # 입력이 파일 경로일 경우, 파일 존재 여부를 확인합니다.
        if isinstance(audio_path_or_data, str) and not os.path.exists(audio_path_or_data):
            logger.error(f"STT 변환을 위한 오디오 파일을 찾을 수 없습니다: {audio_path_or_data}")
            return ""

        result = model.transcribe(audio_path_or_data, language=language, fp16=False)
        transcribed_text = result["text"].strip()

        processing_time = (time.time() - start_time) * 1000
        logger.info(f"✅ STT 변환 완료 ({processing_time:.2f}ms). 결과: '{transcribed_text[:50]}...'")
        
        return transcribed_text
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        logger.error(f"❌ STT 변환 중 오류가 발생했습니다 ({processing_time:.2f}ms): {e}", exc_info=True)
        # STT 실패 시 빈 문자열을 반환합니다.
        return ""
