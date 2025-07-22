# main.py - FastAPI 백엔드 서버
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import base64
import numpy as np
import whisper
from TTS.api import TTS
import io
import soundfile as sf
import torch
import librosa

app = FastAPI(title="실시간 음성 대화 서비스")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 오픈소스 모델 초기화
whisper_model = whisper.load_model("base")  # OpenAI Whisper
tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device='cuda')  # Coqui TTS

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

@app.get("/ping")
async def ping():
    return "pong"

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 클라이언트로부터 음성 데이터 수신
            print('시작')
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "audio":
                # Base64 음성 데이터 디코딩
                audio_data = base64.b64decode(message["data"])
                print("[수신] : 오디오 길이", len(audio_data))
                # STT 처리 (Whisper)
                text = await process_speech_to_text(audio_data)
                print(text)
                if text:
                    # LLM 처리
                    reply = await process_llm_response(text)
                    # TTS 처리 (Coqui TTS)
                    audio_response = await process_text_to_speech(reply)
                    
                    # 응답 전송
                    response = {
                        "type": "response",
                        "text": reply,
                        "audio": base64.b64encode(audio_response).decode()
                    }
                    await manager.send_message(json.dumps(response), websocket)
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Whisper 전처리 및 STT
async def process_speech_to_text(audio_data: bytes) -> str:
    try:
        with io.BytesIO(audio_data) as f:
            wav_np, sr = sf.read(f, dtype='float32')

        if wav_np.ndim > 1:
            wav_np = np.mean(wav_np, axis=1)  # Stereo → Mono

        if sr != 16000:
            wav_np = librosa.resample(wav_np, orig_sr=sr, target_sr=16000)
            sr = 16000

        # Whisper는 float32 PCM np.array 입력 기대
        audio_np = np.ascontiguousarray(wav_np, dtype=np.float32).copy()

        # NaN 검사
        if np.isnan(audio_np).any():
            print("❗NaN 포함된 오디오")
            return ""

        result = whisper_model.transcribe(audio_np)
        return result.get("text", "")
    except Exception as e:
        print(f"❌ STT 오류: {e}")
        return ""


# Hugging Face LLM 사용
async def process_llm_response(user_input: str) -> str:
    try:
        from transformers import pipeline
        generator = pipeline("text-generation", model="mistralai/Mistral-7B-Instruct-v0.1", device=0 if torch.cuda.is_available() else -1)
        outputs = generator(user_input, max_length=100, do_sample=True)
        return outputs[0]["generated_text"]
    except Exception as e:
        print(f"❌ LLM 오류: {e}")
        return "죄송합니다. 답변 생성에 실패했습니다."

# TTS 처리
async def process_text_to_speech(text: str) -> bytes:
    try:
        audio = tts_model.tts(text)  # numpy float32
        audio_bytes = (audio * 32767).astype(np.int16).tobytes()
        return audio_bytes
    except Exception as e:
        print(f"❌ TTS 오류: {e}")
        return b""

if __name__ == "__main__":
    import uvicorn
    print("🚀 FastAPI 서버 시작 중...")
    uvicorn.run(app, host="0.0.0.0", port=8000)