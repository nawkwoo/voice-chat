"""
LLM (Large Language Model) 서비스

이 모듈은 대규모 언어 모델을 로드하고, 주어진 텍스트(프롬프트)를 기반으로
자연어 응답을 생성하는 기능을 제공합니다.
"""

import time
from typing import Optional, Tuple
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger("llm")

# --- 전역 모델 캐시 ---
# 모델과 토크나이저를 메모리에 한 번만 로드하여 재사용하기 위한 전역 변수입니다.
# 이를 통해 매번 API 요청 시마다 모델을 새로 로드하는 오버헤드를 방지합니다.
_tokenizer: Optional[AutoTokenizer] = None
_llm_model: Optional[AutoModelForCausalLM] = None


def get_llm_models(model_id: Optional[str] = None) -> Tuple[Optional[AutoTokenizer], Optional[AutoModelForCausalLM]]:
    """
    LLM 모델과 토크나이저를 지연 로드(lazy loading)하고 전역적으로 캐싱합니다.

    이 함수는 애플리케이션 시작 시가 아닌, 실제 LLM 기능이 처음 필요할 때 모델을
    메모리에 로드합니다. 이를 통해 초기 구동 시간을 단축하고 메모리를 효율적으로 사용합니다.
    한 번 로드된 모델과 토크나이저는 전역 변수에 캐시되어 이후 요청에서는 즉시 반환됩니다.

    - `settings.LLM_ENABLED`가 `False`이면 모델을 로드하지 않고 `(None, None)`을 반환합니다.
    - `device_map="auto"` 설정을 통해 가능한 경우 GPU(CUDA)를 자동으로 사용하며,
      GPU가 없으면 CPU를 사용합니다.
    - Gemma 계열 모델의 경우 `torch.bfloat16` 데이터 타입을 사용하여 메모리 사용량을 최적화합니다.

    Args:
        model_id (str, optional): 로드할 모델의 Hugging Face ID.
                                    제공되지 않으면 `settings.LLM_MODEL`의 값을 사용합니다.

    Returns:
        Tuple[Optional[AutoTokenizer], Optional[AutoModelForCausalLM]]:
            성공 시 (토크나이저, 모델) 튜플, 실패 또는 비활성화 시 (None, None)을 반환합니다.
    """
    global _tokenizer, _llm_model
    
    if not settings.LLM_ENABLED:
        logger.info("LLM 기능이 비활성화되어 있어 모델을 로드하지 않습니다.")
        return None, None
    
    # 모델이 아직 로드되지 않았을 때만 초기화 수행
    if _llm_model is None:
        model_id = model_id or settings.LLM_MODEL
        logger.info(f"🔄 LLM 모델('{model_id}')의 지연 로딩을 시작합니다...")
        
        try:
            # Gemma 계열 모델 (medgemma, gemma-2 포함)을 위한 설정
            if "gemma" in model_id:
                logger.info(f"Gemma 계열 모델 ('{model_id}')을 로드합니다.")
                _tokenizer = AutoTokenizer.from_pretrained(model_id)
                _llm_model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    torch_dtype=torch.bfloat16,
                    device_map="auto",
                )
            else:
                # 일반 모델 로드
                logger.info(f"일반 LLM 모델 ('{model_id}')을 로드합니다.")
                _tokenizer = AutoTokenizer.from_pretrained(model_id)
                _llm_model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    device_map="auto",
                )
            
            logger.info(f"✅ LLM 모델('{model_id}')이 성공적으로 로드되었습니다.")
        except Exception as e:
            logger.error(f"❌ LLM 모델('{model_id}') 로딩 중 심각한 오류가 발생했습니다: {e}", exc_info=True)
            _tokenizer = None
            _llm_model = None
    
    return _tokenizer, _llm_model


def generate_response(
    prompt: str,
    max_new_tokens: int = 512,
    temperature: float = 0.7,
    repetition_penalty: float = 1.2
) -> str:
    """
    주어진 프롬프트를 기반으로 LLM을 사용하여 텍스트 응답을 생성합니다.

    Args:
        prompt (str): 모델에 입력될 프롬프트 텍스트.
        max_new_tokens (int): 생성될 텍스트의 최대 길이 (토큰 기준).
        temperature (float): 생성의 무작위성을 조절하는 값. 낮을수록 결정론적, 높을수록 다양성이 증가합니다.
        repetition_penalty (float): 응답에서 단어 반복을 억제하는 강도. 1.0 이상으로 설정합니다.

    Returns:
        str: 모델이 생성한 응답 텍스트. 오류 발생 시 대체 메시지를 반환합니다.
    """
    start_time = time.time()
    
    try:
        tokenizer, model = get_llm_models()
        
        if tokenizer is None or model is None:
            logger.warning("LLM 모델이 로드되지 않아 응답을 생성할 수 없습니다.")
            return "죄송합니다. 언어 모델 서비스를 현재 사용할 수 없습니다."

        # MedGemma 모델은 채팅 템플릿 사용
        if "medgemma" in model.name_or_path:
            messages = [
                {"role": "system", "content": "You are a helpful medical assistant."},
                {"role": "user", "content": prompt}
            ]
            inputs = tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_tensors="pt",
            ).to(model.device)
        else:
            # 기존 모델 입력 방식
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

        input_len = inputs["input_ids"].shape[-1]

        # 그래디언트 계산을 비활성화하여 추론 성능을 최적화합니다.
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                pad_token_id=tokenizer.eos_token_id,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
                do_sample=True,  # temperature, top_p, top_k 등의 옵션을 활성화하려면 True로 설정해야 합니다.
                top_k=50,
                top_p=0.95,
            )

        # 생성된 결과에서 입력 프롬프트 부분을 제외하고 순수한 응답만 추출합니다.
        response = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)

        processing_time = (time.time() - start_time) * 1000
        logger.info(f"✅ LLM 응답 생성 완료 ({processing_time:.2f}ms)")

        return response.strip()
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        logger.error(f"❌ LLM 응답 생성 중 오류가 발생했습니다 ({processing_time:.2f}ms): {e}", exc_info=True)
        return f"죄송합니다. 응답을 생성하는 중에 오류가 발생했습니다: {e}"
