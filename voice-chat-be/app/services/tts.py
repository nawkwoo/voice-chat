"""
TTS (Text-to-Speech) 서비스

이 모듈은 `RealTime_zeroshot_TTS_ko` 커스텀 모듈을 사용하여
주어진 텍스트를 자연스러운 한국어 음성으로 변환하는 기능을 제공합니다.
"""

import time
import os
from typing import Optional
from app.settings import settings
from app.utils.logging import get_logger
from app.utils.project_root import PROJECT_ROOT

logger = get_logger("tts")

# --- 전역 모델 캐시 ---
# Custom TTS 모듈을 메모리에 한 번만 로드하여 재사용하기 위한 전역 변수입니다.
# API 요청 시마다 모델을 새로 로드하는 오버헤드를 방지합니다.
_tts_module = None


def get_tts_module():
    """
    Custom TTS (Text-to-Speech) 모듈을 지연 로드(lazy loading)하고 전역적으로 캐싱합니다.

    이 함수는 실제 TTS 기능이 처음 필요할 때 모델을 메모리에 로드하여
    애플리케이션의 초기 구동 시간을 단축하고 메모리 사용을 효율화합니다.
    한 번 로드된 모듈은 전역 변수에 캐시되어 이후 요청에서는 즉시 반환됩니다.

    - `settings.TTS_ENABLED`가 `False`이면 모듈을 로드하지 않고 `None`을 반환합니다.
    - `RealTime_zeroshot_TTS_ko` 모듈을 동적으로 임포트하여 의존성을 분리합니다.
    - 설정 파일에 정의된 참조 화자(reference speaker) 음성 파일을 로드하여
      생성될 음성의 스타일을 결정합니다.

    Returns:
        Custom_TTS 모듈 인스턴스. 로드 실패 또는 비활성화 시 None을 반환합니다.
    """
    global _tts_module

    if not settings.TTS_ENABLED:
        logger.info("TTS 기능이 비활성화되어 있어 모델을 로드하지 않습니다.")
        return None

    if _tts_module is None:
        logger.info("🔄 Custom TTS 모델의 지연 로딩을 시작합니다...")

        try:
            # Custom_TTS 클래스는 이 함수가 처음 호출될 때 동적으로 임포트됩니다.
            # 이를 통해 이 모듈이 없더라도 애플리케이션의 다른 부분은 정상 동작할 수 있습니다.
            from RealTime_zeroshot_TTS_ko.custom_tts import Custom_TTS

            _tts_module = Custom_TTS()
            _tts_module.set_model()  # TTS 모델 자체를 로드

            # 참조 화자의 음성 특성을 로드하여 TTS 음성 스타일을 결정합니다.
            ref_speaker_path = os.path.join(PROJECT_ROOT, settings.TTS_REF_SPEAKER)
            if settings.TTS_REF_SPEAKER and os.path.exists(ref_speaker_path):
                try:
                    _tts_module.get_reference_speaker(speaker_path=ref_speaker_path)
                    logger.info(f"✅ TTS 참조 화자('{ref_speaker_path}')를 성공적으로 로드했습니다.")
                except Exception as e:
                    logger.warning(f"⚠️ TTS 참조 화자 로드에 실패했습니다. 기본 음성으로 대체됩니다: {e}")
            else:
                logger.warning(f"⚠️ TTS 참조 화자 파일('{ref_speaker_path}')을 찾을 수 없습니다. 기본 음성으로 작동합니다.")

            logger.info("✅ Custom TTS 모델이 성공적으로 로드되었습니다.")

        except ModuleNotFoundError:
            logger.error("❌ 'RealTime_zeroshot_TTS_ko' 모듈을 찾을 수 없습니다. TTS 기능을 비활성화합니다.")
            settings.TTS_ENABLED = False
            _tts_module = None  # 실패 시 명시적으로 None으로 설정
            return None

        except Exception as e:
            logger.error(f"❌ Custom TTS 모델 로딩 중 심각한 오류가 발생했습니다: {e}", exc_info=True)
            settings.TTS_ENABLED = False
            _tts_module = None  # 실패 시 명시적으로 None으로 설정
            return None

    return _tts_module


def text_to_speech(text: str) -> Optional[bytes]:
    """
    주어진 텍스트를 음성 오디오 데이터(bytes)로 변환합니다.

    - TTS 모듈이 성공적으로 로드된 경우, 이를 사용하여 음성을 생성합니다.
    - 모듈 로드 실패 또는 TTS 변환 과정에서 오류 발생 시,
      `None`을 반환하여 호출 측에서 오류를 인지하고 처리하도록 합니다.
      (예: 더미 오디오 생성 또는 클라이언트에게 알림)

    Args:
        text (str): 음성으로 변환할 텍스트.

    Returns:
        Optional[bytes]: 생성된 WAV 형식의 오디오 데이터. 실패 시 None.
    """
    start_time = time.time()

    try:
        tts_module = get_tts_module()

        if tts_module is None:
            logger.warning("TTS 모듈을 사용할 수 없어 오디오를 생성할 수 없습니다.")
            return None

        # Custom TTS 모듈을 사용하여 텍스트로부터 음성 파일 생성
        # 이 함수는 생성된 오디오 파일의 경로를 반환합니다.
        # 텍스트가 비어있으면 빈 오디오를 반환할 수 있으므로 확인
        if not text or not text.strip():
            logger.warning("TTS를 위한 텍스트가 비어있어 오디오를 생성하지 않습니다.")
            return None

        audio_file_path = tts_module.make_speech(text)

        if not audio_file_path or not os.path.exists(audio_file_path):
            logger.error("TTS 모듈이 오디오 파일을 생성하지 못했습니다.")
            return None

        # 생성된 파일을 바이너리 모드로 읽어 bytes 데이터로 변환
        with open(audio_file_path, 'rb') as f:
            audio_data = f.read()

        # 임시로 생성된 오디오 파일 삭제
        os.remove(audio_file_path)

        processing_time = (time.time() - start_time) * 1000
        logger.info(f"✅ TTS 변환 완료. 생성된 오디오 크기: {len(audio_data)} bytes ({processing_time:.2f}ms)")

        return audio_data

    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        logger.error(f"❌ TTS 변환 중 오류가 발생했습니다 ({processing_time:.2f}ms): {e}", exc_info=True)
        return None

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
