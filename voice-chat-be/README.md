# Voice Chat Backend

실시간 음성 대화 서비스를 위한 FastAPI 백엔드

## 🏗️ 프로젝트 구조

```
voice-chat-be/
├─ app/                          # 메인 애플리케이션
│  ├─ main.py                    # FastAPI 엔트리 포인트
│  ├─ settings.py                # 환경 설정 관리
│  ├─ deps.py                    # 의존성 주입
│  ├─ database/                  # 데이터베이스 관련
│  │   ├─ session.py             # DB 세션 관리
│  │   └─ models.py              # SQLAlchemy 모델
│  ├─ services/                  # 비즈니스 로직 서비스
│  │   ├─ stt.py                 # Speech-to-Text (Whisper)
│  │   ├─ tts.py                 # Text-to-Speech (Custom TTS)
│  │   ├─ llm.py                 # Large Language Model
│  │   ├─ conversation.py        # 대화 관리 서비스
│  │   └─ users.py               # 사용자 관리 서비스
│  ├─ routers/                   # API 라우터
│  │   ├─ health.py              # 헬스체크 API
│  │   ├─ sessions.py            # 세션 관리 API
│  │   ├─ tts_api.py             # TTS API
│  │   └─ voice_chat.py          # 음성 채팅 API
│  ├─ utils/                     # 유틸리티
│  │   ├─ audio.py               # 오디오 처리
│  │   └─ logging.py             # 로깅 설정
│  └─ ws/                        # WebSocket
│      └─ manager.py             # WebSocket 연결 관리
├─ RealTime_voicechat/           # 기존 모듈 (유지)
├─ RealTime_zeroshot_TTS_ko/     # Custom TTS 모듈
├─ docker-compose.yml            # Docker Compose 설정
├─ Dockerfile                    # Docker 이미지 설정
├─ requirements.txt              # Python 의존성
├─ env.local                     # 로컬 개발용 환경 설정
├─ env.docker                    # 도커용 환경 설정
├─ certs/                        # SSL 인증서 (선택)
├─ processed/                    # 출력물/임시 파일
└─ init-scripts/                 # MariaDB 초기화 스크립트
```

## 🚀 실행 방법

### 1. 의존성만 도커로 실행

```bash
# MariaDB, Milvus, MinIO, etcd만 도커로 실행
docker compose up -d mariadb milvus-minio milvus-etcd milvus-standalone

# 상태 확인
docker compose ps
```

### 2. 로컬에서 백엔드 실행

```bash
# Python 가상환경 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 로컬 백엔드 실행
uvicorn app.main:app --reload --port 8000
```

### 3. HTTPS 실행 (선택)

```bash
# SSL 인증서가 있는 경우
uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --ssl-certfile ./certs/cert.pem \
  --ssl-keyfile ./certs/key.pem
```

### 4. 전체 도커 실행

```bash
# 모든 서비스를 도커로 실행
docker compose up -d

# 로그 확인
docker compose logs -f fastapi
```

## 🔧 환경 설정

### 로컬 개발용 (env.local)
```ini
ENVIRONMENT=local
DB_HOST=localhost
DB_PORT=3306
DB_USER=voice_chat_user
DB_PASSWORD=voicechat2024
DB_NAME=voice_chat_db

MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=voice_conversations

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
LOG_LEVEL=INFO

LLM_ENABLED=false
TTS_ENABLED=false
HF_HOME=./.hf_cache
```

### 도커용 (env.docker)
```ini
ENVIRONMENT=docker
DB_HOST=mariadb
DB_PORT=3306
DB_USER=voice_chat_user
DB_PASSWORD=voicechat2024
DB_NAME=voice_chat_db

MILVUS_HOST=milvus-standalone
MILVUS_PORT=19530
MILVUS_COLLECTION=voice_conversations

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
LOG_LEVEL=INFO

LLM_ENABLED=false
TTS_ENABLED=false
HF_HOME=/root/.cache/huggingface

SSL_CRT_FILE=/certs/cert.pem
SSL_KEY_FILE=/certs/key.pem
```

## 📡 API 엔드포인트

### 헬스체크
- `GET /api/ping` - 기본 핑 응답
- `GET /api/health` - 상세 헬스체크 (DB, Milvus 상태)

### 세션 관리
- `POST /api/sessions/new` - 새 세션 생성
- `GET /api/sessions/{user_id}/stats` - 사용자 통계
- `GET /api/sessions/{session_id}/stats` - 세션 통계
- `POST /api/sessions/{session_id}/end` - 세션 종료

### 음성 처리
- `POST /api/tts/synthesize` - 텍스트를 음성으로 변환
- `POST /api/voice-chat` - 음성 파일 업로드 → STT → LLM → TTS

### WebSocket
- `WS /ws/{user_id}/{session_id}` - 실시간 음성 채팅

## 🧪 테스트

### 헬스체크
```bash
curl http://localhost:8000/api/ping
curl http://localhost:8000/api/health
```

### 새 세션 생성
```bash
curl -X POST http://localhost:8000/api/sessions/new
```

### TTS 테스트
```bash
curl -X POST http://localhost:8000/api/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "안녕하세요"}'
```

## 🔍 주요 기능

### 지연 로드 (Lazy Loading)
- **Whisper STT**: 필요할 때만 모델 로드
- **LLM**: 설정에 따라 활성화/비활성화
- **Custom TTS**: MeCab 의존성 문제 해결

### 환경 분리
- **로컬 개발**: 의존성만 도커, 백엔드는 로컬
- **도커 배포**: 전체 서비스를 도커로 실행

### HTTPS 지원
- 인증서 파일 존재 시 자동 HTTPS 활성화
- 로컬에서 uvicorn 옵션으로 쉽게 제어

### 모듈화된 구조
- **서비스**: 비즈니스 로직 분리
- **라우터**: API 엔드포인트 분리
- **설정**: 환경별 설정 관리

## 🐛 문제 해결

### MeCab 오류
```bash
# 도커 컨테이너에서 MeCab 설치
docker exec -it voice_chat_api bash
apt-get update && apt-get install -y mecab-ipadic-utf8
```

### 의존성 충돌
- `faster-whisper` 제거 (tokenizers 충돌)
- `TTS==0.22.0` 제거 (MeCab 의존성)
- MeCab 관련 패키지들 주석 처리

### 포트 충돌
```bash
# 포트 확인
netstat -tulpn | grep :8000
# 또는
lsof -i :8000
```

## 📝 개발 노트

### 변경 사항
1. **Coqui TTS 제거**: MeCab 의존성 문제 해결
2. **지연 로드 유지**: Whisper/LLM/TTS 모두 지연 로드
3. **환경 분리**: 로컬/도커 설정 분리
4. **모듈화**: 서비스/라우터/설정 분리
5. **HTTPS 개선**: 인증서 기반 자동 활성화

### 다음 단계
- [ ] MeCab 설치 자동화
- [ ] TTS 모듈 안정화
- [ ] 성능 최적화
- [ ] 테스트 코드 작성
