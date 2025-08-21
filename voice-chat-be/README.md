# 🗣️ Voice Chat AI Backend

실시간 음성 기반 AI 채팅 서비스의 백엔드 시스템입니다. FastAPI를 기반으로 WebSocket을 통해 실시간 음성 데이터를 처리하고, STT, LLM, TTS 기술을 통합하여 사용자에게 AI와 대화하는 경험을 제공합니다.

## ✨ 주요 기능

- **실시간 음성 스트리밍**: WebSocket을 통해 클라이언트로부터 실시간 음성 데이터를 수신합니다.
- **음성-텍스트 변환 (STT)**: `openai-whisper`를 사용하여 수신된 음성을 텍스트로 변환합니다.
- **대규모 언어 모델 (LLM)**: `Hugging Face Transformers`를 통해 `gemma`와 같은 LLM을 사용하여 텍스트 응답을 생성합니다.
- **텍스트-음성 변환 (TTS)**: `RealTime_zeroshot_TTS_ko` 커스텀 모듈을 사용하여 생성된 텍스트를 자연스러운 음성으로 변환합니다.
- **대화 기록 및 검색**: `Milvus` 벡터 데이터베이스를 사용하여 대화 내용을 벡터로 저장하고 의미 기반 검색을 지원합니다.
- **지연 로딩 (Lazy Loading)**: STT, LLM, TTS 모델을 실제 사용 시점에 메모리에 로드하여 초기 구동 속도를 최적화하고 리소스 사용을 효율화합니다.

## 🏗️ 시스템 아키텍처

본 프로젝트는 Docker Compose를 사용하여 각 컴포넌트를 컨테이너화하여 관리합니다.

- **`voice_chat_api`**: FastAPI 기반의 메인 애플리케이션 서버입니다.
- **`mariadb`**: 사용자 및 세션 정보를 저장하는 관계형 데이터베이스입니다.
- **`milvus-standalone`**: 대화 내용의 벡터 임베딩을 저장하고 검색하는 벡터 DB입니다.
- **`minio`, `etcd`**: Milvus의 의존성 서비스입니다.

## 📁 프로젝트 구조

```
voice-chat-be/
├─ app/                     # FastAPI 애플리케이션 소스 코드
│  ├─ database/             # 데이터베이스 (SQLAlchemy 모델, 세션 관리)
│  ├─ routers/              # API 엔드포인트 (라우터) 정의
│  ├─ services/             # 핵심 비즈니스 로직 (STT, LLM, TTS, 대화 관리)
│  ├─ utils/                # 로깅 등 보조 유틸리티
│  ├─ vector_store/         # Milvus 클라이언트 래퍼
│  ├─ ws/                   # WebSocket 연결 관리
│  ├─ deps.py               # 의존성 주입 (미사용)
│  ├─ main.py               # 애플리케이션 시작점 (entrypoint)
│  ├─ models.py             # Pydantic 데이터 모델 (미사용)
│  └─ settings.py           # 환경 변수 및 설정 관리
├─ RealTime_zeroshot_TTS_ko/  # 커스텀 한국어 TTS 모듈
├─ certs/                   # SSL 인증서 (필요시 사용)
├─ init-scripts/            # MariaDB 초기화 스크립트
├─ docker-compose.yml       # Docker 서비스 정의
├─ Dockerfile               # API 서버 Docker 이미지 빌드 파일
├─ preload_models.py        # (테스트용) AI 모델 사전 로드 스크립트
├─ requirements.txt         # Python 패키지 의존성 목록
└─ README.md                # 프로젝트 안내 문서
```

## 🚀 시작하기

### 사전 준비

- [Docker](https://www.docker.com/products/docker-desktop/) 및 Docker Compose 설치
- `git` 설치
- Hugging Face 계정 및 `HUGGING_FACE_HUB_TOKEN` 발급 (Gemma 등 gated model 사용 시 필요)

### 설치 및 실행

1.  **프로젝트 클론**
    ```bash
    git clone https://your-repository-url.com/voice-chat.git
    cd voice-chat/voice-chat-be
    ```

2.  **환경 변수 설정**
    프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 참고하여 작성합니다. `env.docker` 파일을 복사하여 사용해도 좋습니다.

    ```env
    # --- 데이터베이스 설정 ---
    DB_USER=your_db_user
    DB_PASSWORD=your_db_password
    DB_NAME=your_db_name
    DB_HOST=mariadb  # Docker Compose 서비스 이름
    DB_PORT=3306

    # --- Milvus 설정 ---
    MILVUS_HOST=milvus-standalone # Docker Compose 서비스 이름
    MILVUS_PORT=19530

    # --- AI 모델 설정 ---
    # Hugging Face Hub 로그인 토큰 (Gemma 등 Gated 모델 다운로드 시 필요)
    HUGGING_FACE_HUB_TOKEN="hf_xxxxxxxxxxxxxxxx"
    
    # 사용할 모델 ID
    LLM_MODEL="google/gemma-2b-it"
    EMBEDDING_MODEL="jhgan/ko-sroberta-multitask"
    WHISPER_MODEL="small" # (tiny, base, small, medium, large)

    # 기능 활성화 여부
    LLM_ENABLED=true
    TTS_ENABLED=true
    STT_ENABLED=true
    
    # --- 기타 ---
    ENVIRONMENT=docker
    LOG_LEVEL=INFO
    ```

3.  **도커 컨테이너 빌드 및 실행**
    ```bash
    docker-compose up --build
    ```
    `--build` 옵션은 Dockerfile이나 코드에 변경사항이 있을 때 이미지를 새로 빌드합니다. 최초 실행 시 또는 변경 후 실행 시에 사용합니다.

4.  **서비스 확인**
    - API 서버: `http://localhost:8000`
    - API 문서 (Swagger UI): `http://localhost:8000/docs`

## 📡 API 주요 엔드포인트

- **`WS /ws/voice/{session_id}`**: 실시간 음성 채팅을 위한 WebSocket 엔드포인트입니다.
- **`GET /api/health/`**: 시스템의 주요 구성 요소(DB, Vector DB) 상태를 확인하는 헬스체크 엔드포인트입니다.

## 📝 개발 참고사항

- **AI 모델 캐시**: Hugging Face 모델은 최초 실행 시 다운로드되며, Docker 볼륨(`huggingface_cache`)에 캐시되어 다음 실행부터는 빠르게 로드됩니다.
- **민감 정보**: `.env` 파일은 버전 관리에 포함되지 않도록 `.gitignore`에 등록해야 합니다.
- **메모리 할당**: LLM 등 큰 모델을 사용하는 경우, Docker Desktop의 설정(Settings > Resources)에서 충분한 메모리(최소 8GB 이상 권장)를 할당해야 합니다.
