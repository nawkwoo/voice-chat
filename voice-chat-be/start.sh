#!/bin/bash

echo "🚀 Voice Chat 애플리케이션 시작 스크립트"
echo "=========================================="

# SSL 인증서 확인 및 생성
if [ ! -f "certs/cert.pem" ] || [ ! -f "certs/key.pem" ]; then
    echo "🔐 SSL 인증서 생성 중..."
    chmod +x certs/generate_certs.sh
    ./certs/generate_certs.sh
fi

# Docker Compose 실행
echo "🐳 Docker Compose 시작 중..."
docker-compose up --build -d

echo "⏳ 서비스 시작 대기 중..."
echo "📊 서비스 상태 확인:"
docker-compose ps

# 서비스 준비 대기
echo "⏳ 서비스 준비 대기 중..."
for i in {1..60}; do
    echo -n "."
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo ""
        echo "✅ FastAPI 서비스 준비 완료!"
        break
    fi
    sleep 5
done

# 최종 헬스체크
echo "🔍 최종 헬스체크:"
curl -f http://localhost:8000/health || echo "❌ FastAPI 서비스 응답 없음"

echo ""
echo "✅ Voice Chat 애플리케이션이 시작되었습니다!"
echo "🌐 웹 인터페이스: http://localhost:8000"
echo "📚 API 문서: http://localhost:8000/docs"
echo ""
echo "로그 확인: docker-compose logs -f fastapi"
