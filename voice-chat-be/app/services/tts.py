"""
TTS (Text-to-Speech) 서비스
"""

import time
import os
from typing import Optional
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger("tts")

# --- 전역 모델 캐시 ---
# Custom TTS 모듈을 메모리에 한 번만 로드하여 재사용하기 위한 전역 변수입니다.
# API 요청 시마다 모델을 새로 로드하는 오버헤드를 방지합니다.
_tts_module = None


def get_tts_module():
    """
    Custom TTS (Text-to-Speech) 모듈을 지연 로드(lazy loading)합니다.
    - `TTS_ENABLED` 설정이 `False`이면 모듈을 로드하지 않습니다.
    - 모듈이 아직 로드되지 않은 경우, `Custom_TTS` 클래스를 임포트하고 초기화하여
      전역 변수 `_tts_module`에 캐시합니다.
    - 참조 화자(reference speaker) 음성 파일도 함께 로드합니다.
    
    Returns:
        Custom_TTS 모듈 인스턴스. 로드 실패 또는 비활성화 시 None.
    """
    global _tts_module
    
    if not settings.TTS_ENABLED:
        logger.info("TTS 기능이 비활성화되어 있어 모델을 로드하지 않습니다.")
        return None
    
    if _tts_module is None:
        logger.info("🔄 Custom TTS 모델의 지연 로딩을 시작합니다...")
        
        try:
            # Custom_TTS 클래스는 이 함수가 처음 호출될 때 동적으로 임포트됩니다.
            from RealTime_zeroshot_TTS_ko.custom_tts import Custom_TTS
            
            _tts_module = Custom_TTS()
            _tts_module.set_model() # TTS 모델 자체를 로드
            
            # 참조 화자의 음성 특성을 로드하여 TTS 음성 스타일을 결정합니다.
            if settings.TTS_REF_SPEAKER and os.path.exists(settings.TTS_REF_SPEAKER):
                try:
                    _tts_module.get_reference_speaker(speaker_path=settings.TTS_REF_SPEAKER)
                    logger.info(f"✅ TTS 참조 화자('{settings.TTS_REF_SPEAKER}')를 성공적으로 로드했습니다.")
                except Exception as e:
                    logger.warning(f"⚠️ TTS 참조 화자 로드에 실패했습니다. 기본 음성으로 대체됩니다: {e}")
            else:
                logger.warning(f"⚠️ TTS 참조 화자 파일('{settings.TTS_REF_SPEAKER}')을 찾을 수 없습니다. 기본 음성으로 작동합니다.")

            logger.info("✅ Custom TTS 모델이 성공적으로 로드되었습니다.")
            
        except ModuleNotFoundError:
            logger.error("❌ 'RealTime_zeroshot_TTS_ko' 모듈을 찾을 수 없습니다. TTS 기능을 비활성화합니다.")
            settings.TTS_ENABLED = False
            return None
            
        except Exception as e:
            logger.error(f"❌ Custom TTS 모델 로딩 중 심각한 오류가 발생했습니다: {e}", exc_info=True)
            settings.TTS_ENABLED = False
            return None
    
    return _tts_module


def text_to_speech(text: str) -> bytes:
    """
    주어진 텍스트를 음성 오디오 데이터(bytes)로 변환합니다.
    - TTS 모듈이 성공적으로 로드된 경우, 이를 사용하여 음성을 생성합니다.
    - 모듈 로드 실패 또는 TTS 변환 과정에서 오류 발생 시,
      사용자 경험이 중단되지 않도록 1초 길이의 무음(dummy) 오디오를 생성하여 반환합니다.
      
    Args:
        text (str): 음성으로 변환할 텍스트.
    
    Returns:
        bytes: 생성된 WAV 형식의 오디오 데이터.
    """
    start_time = time.time()
    
    try:
        tts_module = get_tts_module()
        
        if tts_module is None:
            logger.warning("TTS 모듈을 사용할 수 없어 더미(무음) 오디오를 생성합니다.")
            return _generate_dummy_audio()
        
        # Custom TTS 모듈을 사용하여 텍스트로부터 음성 파일 생성
        # 이 함수는 생성된 오디오 파일의 경로를 반환합니다.
        audio_file_path = tts_module.make_speech(text)
        
        # 생성된 파일을 바이너리 모드로 읽어 bytes 데이터로 변환
        with open(audio_file_path, 'rb') as f:
            audio_data = f.read()

        # 임시로 생성된 오디오 파일 삭제
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
        
        processing_time = (time.time() - start_time) * 1000
        logger.info(f"✅ TTS 변환 완료. 생성된 오디오 크기: {len(audio_data)} bytes ({processing_time:.2f}ms)")
        
        return audio_data
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        logger.error(f"❌ TTS 변환 중 오류가 발생했습니다 ({processing_time:.2f}ms): {e}", exc_info=True)
        
        logger.info("오류 발생으로 인해 더미(무음) 오디오를 대신 반환합니다.")
        return _generate_dummy_audio()

def _generate_dummy_audio() -> bytes:
    """
    오류 발생 시 사용할 1초 길이의 무음 WAV 오디오 데이터를 생성합니다.
    이를 통해 클라이언트 측에서 오디오 처리 로직이 중단되는 것을 방지합니다.
    """
    import numpy as np
    import soundfile as sf
    import io
    
    sample_rate = 16000  # 16kHz
    duration = 1.0       # 1초
    samples = int(sample_rate * duration)
    # float32 타입의 0으로 채워진 배열을 생성 (무음)
    audio_data = np.zeros(samples, dtype=np.float32)
    
    # 메모리 내 버퍼에 WAV 형식으로 오디오 데이터 쓰기
    buffer = io.BytesIO()
    sf.write(buffer, audio_data, sample_rate, format='WAV')
    return buffer.getvalue()
