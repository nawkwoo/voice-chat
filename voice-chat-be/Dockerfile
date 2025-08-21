# --- 1. 기반 이미지 설정 ---
# Python 3.10 버전의 slim 이미지를 기반으로 시작합니다.
# 'slim' 태그는 운영에 필요한 최소한의 패키지만 포함하여 이미지 크기를 줄여줍니다.
FROM python:3.10-slim

# --- 2. 환경 변수 설정 ---
# - PYTHONUNBUFFERED=1: Python의 stdout, stderr 버퍼링을 비활성화하여 로그가 즉시 출력되도록 합니다.
# - PYTHONDONTWRITEBYTECODE=1: .pyc 파일을 생성하지 않아 컨테이너 내부를 깔끔하게 유지합니다.
# - HF_HOME: Hugging Face 모델/데이터가 저장될 캐시 디렉토리를 지정합니다.
# - PIP_NO_CACHE_DIR=1: pip이 캐시를 사용하지 않도록 하여 이미지 크기를 최적화합니다.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/root/.cache/huggingface \
    PIP_NO_CACHE_DIR=1

# --- 3. 작업 디렉토리 설정 ---
# 컨테이너 내에서 명령어가 실행될 기본 경로를 /app으로 설정합니다.
WORKDIR /app

# --- 4. 시스템 패키지 설치 ---
# - ffmpeg: 오디오/비디오 처리에 필요한 라이브러리 (pydub, soundfile 등에서 사용).
# - libsndfile1: 오디오 파일 처리에 필요한 라이브러리.
# - build-essential: C/C++ 코드를 컴파일하는 데 필요한 기본 도구 모음 (일부 Python 패키지 설치 시 필요).
# - git: 소스 코드 버전 관리 도구 (일부 의존성 설치 시 필요할 수 있음).
# --no-install-recommends: 필수 패키지만 설치하여 이미지 크기를 줄입니다.
# 설치 후 apt 캐시를 삭제하여 최종 이미지 크기를 더욱 최적화합니다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    build-essential \
    git \
  && rm -rf /var/lib/apt/lists/*

# --- 5. Python 의존성 설치 (캐시 최적화를 위한 단계적 복사) ---

# 단계 5-1: requirements.txt 파일만 먼저 복사하고 의존성을 설치합니다.
# 소스 코드가 변경되어도 requirements.txt가 변경되지 않았다면, Docker는 이 레이어의 캐시를 재사용하여
# 빌드 시간을 크게 단축시킬 수 있습니다.
COPY requirements.txt ./

ARG CACHE_BUSTER=1
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir --upgrade --force-reinstall -r requirements.txt

# Hugging Face CLI를 사용하여 강제로 로그인하여 인증 문제를 해결합니다.
# 이 단계는 빌드 시점에 --build-arg HF_TOKEN=... 형식으로 토큰을 전달받습니다.
ARG HF_TOKEN
RUN apt-get update && apt-get install -y git-lfs && git-lfs install
RUN if [ -n "$HF_TOKEN" ]; then hf auth login --token "$HF_TOKEN" --add-to-git-credential; else echo "HF_TOKEN not provided, skipping login"; fi

# 단계 5-2: 의존성 설치가 완료된 후, 전체 애플리케이션 소스 코드를 복사합니다.
# 이 방식은 로컬 파일 시스템의 변경사항이 즉시 반영되지는 않지만,
# 이미지의 일관성과 재현성을 보장하여 경로 문제를 원천적으로 차단합니다.
COPY . .

# Real-Time-TTS 모듈 내의 MeloTTS를 설치합니다.
RUN pip install -e /app/RealTime_zeroshot_TTS_ko/MeloTTS

# --- 6. 포트 노출 ---
# 컨테이너의 8000번 포트를 외부에 노출시켜 FastAPI 애플리케이션에 접근할 수 있도록 합니다.
EXPOSE 8000

# --- 7. 컨테이너 실행 명령어 ---
# 컨테이너가 시작될 때 실행될 기본 명령어를 정의합니다.
# /certs/ 경로에 SSL 인증서와 키 파일이 존재하는지에 따라 HTTPS 또는 HTTP 모드로 Uvicorn 서버를 실행합니다.
# - --proxy-headers: 리버스 프록시(예: Nginx, Traefik) 뒤에서 실행될 때 클라이언트의 실제 IP와 프로토콜을 올바르게 인식하도록 돕습니다.
# - --forwarded-allow-ips='*': 모든 프록시로부터의 forwarded 헤더를 신뢰합니다 (필요에 따라 특정 IP로 제한).
CMD ["sh", "-c", "if [ -f /certs/cert.pem ] && [ -f /certs/key.pem ]; then \
  echo '🚀 Found SSL certificates. Starting server in HTTPS mode...'; \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --ssl-certfile /certs/cert.pem --ssl-keyfile /certs/key.pem --proxy-headers --forwarded-allow-ips='*'; \
  else \
  echo '🚀 No SSL certificates found. Starting server in HTTP mode...'; \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'; fi"]