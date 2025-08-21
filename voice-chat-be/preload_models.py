"""
Hugging Face 모델 및 기타 AI 모델을 미리 다운로드하고 캐시하는 스크립트.
Dockerfile에서 이 스크립트를 실행하여 빌드 시점에 모델을 이미지에 포함시킵니다.
"""
import os
import torch
from app.settings import settings
from transformers import AutoTokenizer, AutoModelForCausalLM
from huggingface_hub import login

def huggingface_login():
    """Hugging Face Hub에 프로그래매틱하게 로그인합니다."""
    print("🔄 Hugging Face Hub에 로그인 시도...")
    try:
        token = settings.HUGGING_FACE_HUB_TOKEN
        if not token:
            print("⚠️ .env 파일에 HUGGING_FACE_HUB_TOKEN이 설정되지 않았습니다.")
            return False
        login(token=token, add_to_git_credential=False)
        print("✅ Hugging Face Hub 로그인 성공!")
        return True
    except Exception as e:
        print(f"❌ Hugging Face Hub 로그인 실패: {e}")
        return False

def preload_stt_model():
    """STT (Whisper) 모델 사전 로드"""
    print("🔄 STT 모델 사전 로드 시작...")
    try:
        from whisper import load_model
        model_name = settings.WHISPER_MODEL or "small"
        load_model(model_name)
        print(f"✅ STT 모델 '{model_name}' 사전 로드 완료")
    except Exception as e:
        print(f"❌ STT 모델 사전 로드 실패: {e}")

def preload_llm_model():
    """LLM (CausalLM) 모델 사전 로드"""
    print("🔄 LLM 모델 사전 로드 시작...")
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        # settings.py에서 모델 ID를 가져오도록 수정
        model_id = settings.LLM_MODEL
        
        # MedGemma 또는 Gemma 계열 모델을 위한 특별 처리
        if "gemma" in model_id:
            print(f"Gemma 계열 모델 ('{model_id}')을 로드합니다.")
            AutoTokenizer.from_pretrained(model_id)
            AutoModelForCausalLM.from_pretrained(
                model_id,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
        else:
            # 일반 모델 로드
            print(f"일반 LLM 모델 ('{model_id}')을 로드합니다.")
            AutoTokenizer.from_pretrained(model_id, use_fast=False)
            AutoModelForCausalLM.from_pretrained(model_id)
            
        print(f"✅ LLM 모델 '{model_id}' 사전 로드 완료")
    except Exception as e:
        print(f"❌ LLM 모델 사전 로드 실패: {e}")

def preload_tts_model():
    """TTS (MeloTTS) 모델 사전 로드"""
    print("🔄 TTS 모델 사전 로드 시작...")
    try:
        from MeloTTS.melo.api import TTS
        speed = 1.0
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 모델 경로 설정
        model_path = os.path.join(settings.CHECKPOINTS_DIR, settings.TTS_MODEL_VERSION)
        
        # 모델 로드 (MeloTTS는 내부적으로 필요한 파일을 다운로드 함)
        TTS(language=settings.TTS_LANGUAGE, device=device, ckpt_path=model_path)
        print(f"✅ TTS 모델 '{settings.TTS_MODEL_VERSION}' 사전 로드 완료")
    except Exception as e:
        print(f"❌ TTS 모델 사전 로드 실패: {e}")


def preload_embedding_model():
    """VectorDB용 임베딩 모델 사전 로드"""
    print("🔄 임베딩 모델 사전 로드 시작...")
    try:
        from sentence_transformers import SentenceTransformer
        model_name = settings.EMBEDDING_MODEL
        SentenceTransformer(model_name)
        print(f"✅ 임베딩 모델 '{model_name}' 사전 로드 완료")
    except Exception as e:
        print(f"❌ 임베딩 모델 사전 로드 실패: {e}")


if __name__ == "__main__":
    print("🚀 AI 모델 사전 로드를 시작합니다...")
    
    # Hugging Face 로그인 먼저 수행
    if not huggingface_login():
        print("🛑 Hugging Face 로그인이 필요하므로 모델 로드를 중단합니다.")
    else:
        # settings.py의 기본 경로를 사용하여 모델 로드
        # Docker 빌드 환경에서는 환경 변수가 없을 수 있으므로 기본값을 사용합니다.
        
        preload_stt_model()
        preload_llm_model()
        # preload_tts_model() # TTS는 체크포인트 경로 문제로 빌드 시 실행이 복잡할 수 있어 일단 제외
        preload_embedding_model()
        
        print("🎉 모든 AI 모델 사전 로드를 완료했습니다.")
