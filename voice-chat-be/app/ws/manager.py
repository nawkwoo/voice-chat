"""
WebSocket 연결 관리자
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
from app.services.tts import text_to_speech
from app.services.conversation import get_conversation_service, add_message_with_vector, get_session_stats
from app.services.users import get_user_stats
from app.utils.logging import get_logger
import numpy as np
import tempfile
import os

logger = get_logger("websocket")


class ConnectionManager:
    """
    활성 WebSocket 연결을 관리하는 중앙 관리자 클래스입니다.
    - 연결 수락, 정보 저장, 연결 종료를 처리합니다.
    - 특정 클라이언트에게 메시지를 보내는 유틸리티 메서드를 제공합니다.
    """
    
    def __init__(self):
        """ConnectionManager를 초기화합니다."""
        # 활성 연결을 저장하는 딕셔너리. Key: WebSocket 객체, Value: 연결 정보 딕셔너리
        self.active_connections: Dict[WebSocket, Dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, session_id: str):
        """
        새로운 클라이언트의 WebSocket 연결을 수락하고 관리 목록에 추가합니다.
        """
        await websocket.accept()
        
        # 연결 정보를 딕셔너리에 저장
        self.active_connections[websocket] = {
            "user_id": user_id,
            "session_id": session_id,
            "connected_at": datetime.utcnow()
        }
        
        logger.info(f"🔗 WebSocket 클라이언트 연결됨: 사용자 {user_id} (세션: {session_id})")
        return self.active_connections[websocket]
    
    def disconnect(self, websocket: WebSocket):
        """
        클라이언트의 WebSocket 연결을 종료하고 관리 목록에서 제거합니다.
        연결 종료 시, 해당 대화 세션을 '종료' 상태로 업데이트합니다.
        """
        if websocket in self.active_connections:
            connection_info = self.active_connections.pop(websocket) # pop으로 제거와 조회를 동시에
            
            # 대화 세션을 종료 상태로 변경
            try:
                conversation_service = get_conversation_service()
                if conversation_service:
                    # 의존성 주입을 사용하지 않으므로 직접 DB 세션을 생성하고 닫아줘야 함
                    db = next(get_db())
                    try:
                        conversation_service.end_session(db, connection_info["session_id"])
                    finally:
                        db.close()
            except Exception as e:
                logger.warning(f"세션({connection_info['session_id']}) 종료 처리 중 오류 발생: {e}")
            
            logger.info(f"🔌 WebSocket 클라이언트 연결 끊김: 사용자 {connection_info['user_id']}")
    
    def get_connection_info(self, websocket: WebSocket) -> Dict:
        """특정 WebSocket 연결의 저장된 정보를 조회합니다."""
        return self.active_connections.get(websocket, {})
    
    async def send_json(self, data: Dict, websocket: WebSocket):
        """딕셔너리 데이터를 JSON 문자열로 변환하여 특정 클라이언트에게 전송합니다."""
        await websocket.send_text(json.dumps(data))


# --- 전역 매니저 인스턴스 ---
# 애플리케이션 전체에서 단일 인스턴스로 사용될 ConnectionManager를 생성합니다.
manager = ConnectionManager()


async def handle_websocket_message(websocket: WebSocket, user_id: str, session_id: str, data: str):
    """
    클라이언트로부터 받은 WebSocket 메시지를 파싱하고 타입에 따라 적절한 핸들러로 분기합니다.
    - `audio`: 음성 데이터 처리 파이프라인 실행
    - `get_stats`: 통계 정보 조회 및 전송
    """
    try:
        message = json.loads(data)
        msg_type = message.get("type")

        if msg_type == "audio":
            await handle_audio_message(websocket, user_id, session_id, message)
        elif msg_type == "get_stats":
            await handle_get_stats(websocket, user_id, session_id)
        else:
            logger.warning(f"알 수 없는 WebSocket 메시지 타입 수신: {msg_type}")
            await manager.send_json({"type": "error", "message": "Unknown message type"}, websocket)
            
    except json.JSONDecodeError:
        logger.error("잘못된 JSON 형식의 WebSocket 메시지를 수신했습니다.")
        await manager.send_json({"type": "error", "message": "Invalid JSON format"}, websocket)
    except Exception as e:
        logger.error(f"WebSocket 메시지 처리 중 예기치 않은 오류 발생: {e}", exc_info=True)
        await manager.send_json({"type": "error", "message": str(e)}, websocket)

async def handle_audio_message(websocket: WebSocket, user_id: str, session_id: str, message: Dict):
    """
    'audio' 타입의 메시지를 처리하는 파이프라인입니다.
    STT -> LLM -> TTS 순서로 음성 채팅을 진행합니다.
    """
    audio_b64 = message.get("data")
    if not audio_b64:
        logger.warning("'audio' 타입 메시지에 'data' 필드가 없습니다.")
        return

    audio_data = base64.b64decode(audio_b64)
    logger.info(f"[수신] 오디오 데이터 (세션: {session_id}), 크기: {len(audio_data)} bytes")
    
    # 오디오 데이터를 임시 파일로 저장
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        logger.info(f"오디오 데이터를 임시 파일로 저장했습니다: {temp_file_path}")

        # STT (음성 -> 텍스트), 파일 경로 전달
        text = transcribe(temp_file_path)
        logger.info(f"[STT] 변환 결과 (세션: {session_id}): '{text}'")
        
        if text and text.strip():
            # LLM (텍스트 -> 텍스트 응답)
            reply = await process_llm_response(text, user_id, session_id)
            
            # TTS (텍스트 응답 -> 음성)
            audio_response = text_to_speech(reply)
            
            # 최종 응답을 클라이언트에 전송
            response_payload = {
                "type": "response",
                "text": reply,
                "audio": base64.b64encode(audio_response).decode(),
                "user_input": text,
            }
            await manager.send_json(response_payload, websocket)
            logger.info(f"[전송] 음성 응답 (세션: {session_id}), 크기: {len(audio_response)} bytes")
        else:
            logger.warning(f"⚠️ STT 결과가 비어있어 LLM/TTS 처리를 건너뜁니다 (세션: {session_id}).")
            # 인식 실패 정보를 클라이언트에 전송하여 대기 상태 해제
            await manager.send_json({
                "type": "info",
                "message": "음성을 인식하지 못했습니다. 다시 말씀해주세요."
            }, websocket)
    finally:
        # 사용한 임시 파일 삭제
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.info(f"임시 오디오 파일을 삭제했습니다: {temp_file_path}")


async def handle_get_stats(websocket: WebSocket, user_id: str, session_id: str):
    """'get_stats' 타입의 메시지를 처리하여 각종 통계 정보를 전송합니다."""
    logger.info(f"통계 정보 요청 수신 (사용자: {user_id}, 세션: {session_id})")
    db = next(get_db())
    try:
        session_stats = get_session_stats(db, session_id)
        user_stats = get_user_stats(user_id, db)

        # Milvus 벡터 스토어 통계 조회
        milvus_stats = {}
        conversation_service = get_conversation_service()
        if conversation_service and conversation_service.vector_store:
            try:
                milvus_stats = conversation_service.vector_store.get_collection_stats()
            except Exception as e:
                logger.warning(f"Milvus 통계 조회 실패: {e}")
                milvus_stats = {"error": "Milvus DB에 연결할 수 없습니다."}

        stats_response = {
            "type": "stats",
            "session": session_stats,
            "user": user_stats,
            "milvus": milvus_stats
        }
        await manager.send_json(stats_response, websocket)
    except Exception as e:
        logger.error(f"통계 조회 처리 중 오류 발생: {e}", exc_info=True)
        await manager.send_json({"type": "error", "message": "통계 조회 중 서버 오류 발생"}, websocket)
    finally:
        db.close()


async def process_llm_response(user_input: str, user_id: str, session_id: str) -> str:
    """
    LLM 응답 생성 및 대화 기록 저장을 담당하는 헬퍼 함수입니다.
    이 함수 내에서 DB 세션을 관리합니다.
    """
    logger.info(f"⚙️ LLM 응답 생성을 시작합니다 (입력: '{user_input[:30]}...')")
    db: Session = next(get_db())
    try:
        conversation_service = get_conversation_service()
        if not conversation_service:
            logger.error("대화 서비스를 초기화할 수 없습니다.")
            return "죄송합니다. 대화 서비스에 문제가 발생했습니다."
        
        # 1. 이전 대화 내용 및 유사 대화를 바탕으로 컨텍스트 구성
        context = conversation_service.get_context_for_llm(user_id, session_id, user_input, db)
        
        # 2. LLM에 전달할 최종 프롬프트 생성
        prompt = f"이전 대화 맥락:\n{context}\n\n사용자 질문: {user_input}\n\n답변:"
        
        # 3. LLM 호출하여 응답 생성
        response = generate_response(prompt)
        logger.info(f"LLM 응답 생성 완료: '{response[:50]}...'")
        
        # 4. 사용자 발화와 AI 응답을 DB에 기록
        conversation_service.add_message_with_vector(db, session_id, user_id, "user", user_input)
        if response:
            conversation_service.add_message_with_vector(db, session_id, user_id, "assistant", response)
        
        return response
        
    except Exception as e:
        logger.error(f"LLM 응답 처리 중 오류가 발생했습니다: {e}", exc_info=True)
        return f"죄송합니다, 답변을 생성하는 동안 오류가 발생했습니다: {e}"
    finally:
        db.close()


def webm_bytes_to_np(audio_bytes: bytes) -> np.ndarray:
    """
    브라우저에서 주로 사용하는 WebM 형식의 오디오 데이터(bytes)를
    Whisper 모델이 입력으로 받을 수 있는 NumPy 배열로 변환합니다.
    
    1. `pydub`을 사용하여 WebM 파일을 로드합니다.
    2. 오디오를 모델 요구사항에 맞는 형식(16kHz, 16-bit, 모노)으로 변환합니다.
    3. 변환된 오디오를 메모리 상의 WAV 버퍼로 export합니다.
    4. `soundfile`을 사용하여 WAV 버퍼를 NumPy 배열로 읽어들입니다.
    """
    import io
    import soundfile as sf
    from pydub import AudioSegment

    try:
        # 1. pydub으로 WebM 데이터 로드 -> 포맷을 명시하지 않아 자동으로 감지하도록 변경
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
        
        # 2. 오디오 포맷 변환 (16kHz 샘플레이트, 16-bit, 모노 채널)
        audio_segment = audio_segment.set_frame_rate(16000)
        audio_segment = audio_segment.set_sample_width(2) # 16-bit
        audio_segment = audio_segment.set_channels(1)   # Mono
        
        # 3. 메모리 내 WAV 버퍼로 변환
        wav_buffer = io.BytesIO()
        audio_segment.export(wav_buffer, format="wav")
        wav_buffer.seek(0)
        
        # 4. soundfile로 NumPy 배열(float32)로 최종 변환
        audio_np, _ = sf.read(wav_buffer, dtype='float32')
        
        # 5. 오디오 데이터 정규화 (-1.0 ~ 1.0 범위)
        # Whisper 모델은 float32 타입의 정규화된 오디오 입력에서 최상의 성능을 보입니다.
        audio_np = audio_np.astype(np.float32) / 32768.0
        
        return audio_np
        
    except Exception as e:
        logger.error(f"❌ WebM 오디오 변환 중 오류가 발생했습니다: {e}", exc_info=True)
        # 변환 실패 시, 후속 처리에서 오류가 나지 않도록 빈 배열을 반환합니다.
        return np.array([], dtype=np.float32)
