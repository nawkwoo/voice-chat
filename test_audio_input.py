import asyncio
import base64
import json
import requests
import websockets
import uuid
import ssl

# --- 설정 ---
BASE_URL = "https://localhost:8000"  # FastAPI 서버 주소
WEBSOCKET_URL_FORMAT = "wss://localhost:8000/ws?user_id={user_id}&session_id={session_id}"
AUDIO_FILE_PATH = "voice-chat-be/ttsmaker-file-2025-7-23-12-56-21.mp3"
USER_ID = f"test_user_{uuid.uuid4()}"

async def run_test():
    """
    오디오 파일 입력을 테스트하는 메인 함수
    """
    print(f"🎙️  '{AUDIO_FILE_PATH}' 파일을 AI 음성 비서에게 보내 테스트를 시작합니다.")
    print(f"👤 사용자 ID: {USER_ID}")

    # 1. 새로운 대화 세션 생성
    session_id = None
    try:
        print("\n[1/4] 🚀 새로운 대화 세션을 생성합니다...")
        response = requests.post(
            f"{BASE_URL}/api/sessions/new",
            json={"user_id": USER_ID},
            verify=False  # 로컬 테스트용 self-signed 인증서 허용
        )
        response.raise_for_status()
        session_data = response.json()
        session_id = session_data.get("session_id")
        if not session_id:
            print("❌ 오류: 응답에서 세션 ID를 찾을 수 없습니다.")
            return
        print(f"✅ 성공! 세션 ID: {session_id}")

    except requests.exceptions.RequestException as e:
        print(f"❌ 오류: 새 세션 생성에 실패했습니다. 서버가 실행 중인지 확인하세요. ({e})")
        return

    # 2. 오디오 파일 읽기 및 인코딩
    try:
        print(f"\n[2/4] 🎵 오디오 파일('{AUDIO_FILE_PATH}')을 읽고 인코딩합니다...")
        with open(AUDIO_FILE_PATH, "rb") as f:
            audio_data = f.read()
        base64_audio = base64.b64encode(audio_data).decode('utf-8')
        print("✅ 성공!")
    except FileNotFoundError:
        print(f"❌ 오류: '{AUDIO_FILE_PATH}' 파일을 찾을 수 없습니다.")
        return
    except Exception as e:
        print(f"❌ 오류: 파일을 처리하는 중 문제가 발생했습니다. ({e})")
        return

    # 3. WebSocket 연결 및 오디오 데이터 전송
    websocket_url = WEBSOCKET_URL_FORMAT.format(user_id=USER_ID, session_id=session_id)
    print(f"\n[3/4] 📡 WebSocket에 연결하고({websocket_url}) 오디오를 전송합니다...")
    
    try:
        # ssl_context는 로컬 self-signed 인증서를 신뢰하도록 설정
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with websockets.connect(
            websocket_url, 
            ssl=ssl_context,
            ping_interval=300,  # 5분마다 연결 확인 핑 전송
            ping_timeout=300    # 핑에 대한 응답을 5분간 기다림
        ) as websocket:
            print("✅ WebSocket 연결 성공!")
            
            message_to_send = json.dumps({
                "type": "audio",
                "data": base64_audio
            })
            
            await websocket.send(message_to_send)
            print("✅ 오디오 데이터 전송 완료! AI의 응답을 기다립니다...")

            # 4. 서버로부터 응답 수신
            print("\n[4/4] 🤖 AI 응답 수신 중...")
            response = await websocket.recv()
            response_data = json.loads(response)

            print("\n🎉 테스트 성공! AI 응답을 받았습니다. 🎉")
            print("-" * 50)
            
            if response_data.get("type") == "response":
                print(f"👤 사용자 입력 (STT 변환): '{response_data.get('user_input')}'")
                print(f"🤖 AI 응답 (텍스트): '{response_data.get('text')}'")
                
                # 수신된 오디오 데이터 디코딩 및 저장
                if response_data.get("audio"):
                    audio_response_bytes = base64.b64decode(response_data["audio"])
                    output_filename = "ai_response.wav"
                    with open(output_filename, "wb") as f:
                        f.write(audio_response_bytes)
                    print(f"🔊 AI 음성 응답이 '{output_filename}' 파일로 저장되었습니다.")
                
            elif response_data.get("type") == "error":
                 print(f"⚠️ 서버 오류 응답: {response_data.get('message')}")
            
            else:
                print(f"🔍 알 수 없는 타입의 응답: {response_data}")

            print("-" * 50)

    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ 오류: WebSocket 연결이 닫혔습니다. ({e})")
    except Exception as e:
        print(f"❌ 오류: WebSocket 통신 중 문제가 발생했습니다. ({e})")

if __name__ == "__main__":
    # Windows에서 asyncio 실행 시 필요한 이벤트 루프 정책 설정
    if asyncio.get_event_loop().is_running():
         asyncio.create_task(run_test())
    else:
         asyncio.run(run_test())
