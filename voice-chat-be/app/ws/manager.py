"""
WebSocket 연결 관리자

이 모듈은 활성 WebSocket 연결을 중앙에서 관리하고,
수신되는 메시지를 처리하는 로직을 포함합니다.
"""

import json
import base64
from datetime import datetime
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from app.deps import get_db
from app.services.stt import transcribe
from app.services.llm import generate_response
from app.services.tts import text_to_speech, _generate_dummy_audio
from app.services.conversation_service import get_conversation_service, ConversationService
from app.utils.logging import get_logger
import numpy as np
import tempfile
import os

logger = get_logger("websocket")


class ConnectionManager:
    """
    활성 WebSocket 연결을 관리하는 중앙 관리자 클래스입니다.

    - `active_connections`: 현재 연결된 모든 클라이언트의 WebSocket 객체와 관련 정보
      (user_id, session_id 등)를 딕셔너리 형태로 저장합니다.
    - 연결 수락, 정보 저장, 연결 종료를 처리합니다.
    - 특정 클라이언트에게 메시지를 보내는 유틸리티 메서드를 제공합니다.
    """

    def __init__(self):
        """ConnectionManager를 초기화합니다."""
        # 활성 연결을 저장하는 딕셔너리.
        # Key: WebSocket 객체, Value: 연결 정보 딕셔너리
        self.active_connections: Dict[WebSocket, Dict] = {}

    async def connect(self, websocket: WebSocket, user_id: str, session_id: str):
        """
        새로운 클라이언트의 WebSocket 연결을 수락하고 관리 목록에 추가합니다.
        """
        await websocket.accept()
        self.active_connections[websocket] = {
            "user_id": user_id,
            "session_id": session_id,
        }
        logger.info(f"🔗 WebSocket 클라이언트 연결됨: 사용자 {user_id} (세션: {session_id})")
        # 연결 직후 환영 메시지나 초기 상태 정보를 보낼 수 있습니다.
        await self.send_json({
            "type": "info",
            "message": "서버에 연결되었습니다. 음성 입력을 시작하세요."
        }, websocket)

    def disconnect(self, websocket: WebSocket):
        """
        클라이언트의 WebSocket 연결을 종료하고 관리 목록에서 제거합니다.
        연결이 종료될 때 해당 대화 세션을 '종료' 상태로 업데이트합니다.
        """
        if websocket in self.active_connections:
            connection_info = self.active_connections.pop(websocket)
            session_id = connection_info["session_id"]
            user_id = connection_info["user_id"]

            # DB 작업을 위해 새로운 세션을 생성합니다.
            db: Session = next(get_db())
            try:
                conversation_service = ConversationService(db)
                conversation_service.end_session(session_id)
            except Exception as e:
                logger.error(f"세션 '{session_id}' 종료 처리 중 오류 발생: {e}")
            finally:
                db.close() # 세션을 반드시 닫아줍니다.

            logger.info(f"🔌 WebSocket 클라이언트 연결 끊김: 사용자 {user_id} (세션: {session_id})")

    async def send_json(self, data: Dict, websocket: WebSocket):
        """딕셔너리 데이터를 JSON 문자열로 변환하여 특정 클라이언트에게 전송합니다."""
        if websocket in self.active_connections:
            await websocket.send_text(json.dumps(data))

    async def handle_message(self, websocket: WebSocket, user_id: str, session_id: str, data: str):
        """
        클라이언트로부터 받은 WebSocket 메시지를 파싱하고 타입에 따라 적절한 핸들러로 분기합니다.
        - `audio`: 음성 데이터 처리 파이프라인 실행
        - `get_stats`: (미사용) 통계 정보 조회 및 전송
        """
        try:
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "audio":
                await self._handle_audio_message(websocket, user_id, session_id, message)
            else:
                logger.warning(f"알 수 없는 WebSocket 메시지 타입 수신: {msg_type}")
                await self.send_json({"type": "error", "message": "Unknown message type"}, websocket)
        except json.JSONDecodeError:
            logger.error("잘못된 JSON 형식의 WebSocket 메시지를 수신했습니다.")
            await self.send_json({"type": "error", "message": "Invalid JSON format"}, websocket)
        except Exception as e:
            logger.error(f"WebSocket 메시지 처리 중 예기치 않은 오류 발생: {e}", exc_info=True)
            await self.send_json({"type": "error", "message": str(e)}, websocket)

    async def _handle_audio_message(self, websocket: WebSocket, user_id: str, session_id: str, message: Dict):
        """
        'audio' 타입의 메시지를 처리하는 음성 채팅 파이프라인입니다.
        STT -> LLM -> TTS 순서로 진행되며, 각 단계의 결과를 클라이언트에게 실시간으로 전송합니다.
        """
        audio_b64 = message.get("audio_data")
        if not audio_b64:
            logger.warning("'audio' 메시지에 'audio_data' 필드가 없습니다.")
            return

        audio_bytes = base64.b64decode(audio_b64)
        logger.info(f"[수신] 오디오 데이터 (세션: {session_id}), 크기: {len(audio_bytes)} bytes")

        # --- DB 세션 및 서비스 준비 ---
        db: Session = next(get_db())
        try:
            conversation_service = ConversationService(db)

            # --- 1. STT (음성 -> 텍스트) ---
            # WebM 형식의 오디오 바이트를 NumPy 배열로 변환
            audio_np = _webm_bytes_to_np_array(audio_bytes)
            if audio_np.size == 0:
                raise ValueError("오디오 데이터 변환에 실패했습니다.")

            user_text = transcribe(audio_np, language='ko')
            logger.info(f"[STT] 변환 결과: '{user_text}'")

            # STT 결과를 클라이언트에게 즉시 전송하여 사용자 경험 향상
            await self.send_json({"type": "stt_result", "text": user_text}, websocket)

            if not user_text or not user_text.strip():
                logger.warning("STT 결과가 비어있어 처리를 중단합니다.")
                return

            # 사용자 메시지를 DB에 저장
            conversation_service.add_message(session_id, "user", user_text)

            # --- 2. LLM (텍스트 -> 텍스트 응답) ---
            logger.info("LLM 응답 생성을 시작합니다...")
            context = conversation_service.get_context_for_llm(session_id, user_text)
            prompt = f"### 이전 대화:\n{context}\n\n### 사용자 질문:\n{user_text}\n\n### 답변:"
            ai_response_text = generate_response(prompt)
            logger.info(f"[LLM] 생성된 응답: '{ai_response_text}'")

            if ai_response_text:
                # AI 응답을 DB에 저장
                conversation_service.add_message(session_id, "assistant", ai_response_text)
            else:
                ai_response_text = "죄송합니다, 답변을 생성하지 못했습니다."

            # --- 3. TTS (텍스트 응답 -> 음성) ---
            logger.info("TTS 음성 변환을 시작합니다...")
            audio_response_bytes = text_to_speech(ai_response_text)
            
            # TTS 실패 시, 더미 오디오 생성
            if audio_response_bytes is None:
                logger.warning("TTS 변환 실패. 더미 오디오를 생성합니다.")
                audio_response_bytes = _generate_dummy_audio()


            # --- 4. 최종 음성 응답 전송 ---
            response_payload = {
                "type": "audio_response",
                "text": ai_response_text,
                "audio_data": base64.b64encode(audio_response_bytes).decode('utf-8'),
            }
            await self.send_json(response_payload, websocket)
            logger.info(f"[전송] 최종 음성 응답 (세션: {session_id}), 크기: {len(audio_response_bytes)} bytes")

        except Exception as e:
            logger.error(f"오디오 메시지 처리 파이프라인 오류: {e}", exc_info=True)
            await self.send_json({"type": "error", "message": f"오디오 처리 중 오류 발생: {e}"}, websocket)
        finally:
            # 모든 처리가 끝나면 DB 세션을 닫아줍니다.
            db.close()


def _webm_bytes_to_np_array(audio_bytes: bytes) -> np.ndarray:
    """
    브라우저에서 주로 사용하는 WebM 형식의 오디오 데이터(bytes)를
    Whisper 모델이 입력으로 받을 수 있는 NumPy 배열로 변환합니다.

    `pydub`을 사용하여 WebM을 로드하고, 모델 요구사항에 맞는
    형식(16kHz, 16-bit, 모노)으로 변환한 뒤 NumPy 배열로 반환합니다.
    """
    import io
    import soundfile as sf
    from pydub import AudioSegment

    try:
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
        audio_segment = audio_segment.set_frame_rate(16000)
        audio_segment = audio_segment.set_sample_width(2)  # 16-bit
        audio_segment = audio_segment.set_channels(1)    # Mono

        wav_buffer = io.BytesIO()
        audio_segment.export(wav_buffer, format="wav")
        wav_buffer.seek(0)

        audio_np, _ = sf.read(wav_buffer, dtype='float32')
        return audio_np
    except Exception as e:
        logger.error(f"WebM 오디오 변환 중 오류 발생: {e}", exc_info=True)
        return np.array([], dtype=np.float32)

# 애플리케이션 전역에서 사용할 단일 ConnectionManager 인스턴스
manager = ConnectionManager()
