# Nowhere Data Pipeline - Streamlit 대시보드 컨테이너
# 설계 수준 초안 (실사용 마이그레이션 전 이식성 검증용, 미실행 검증)
# Oracle Linux 8 + SELinux 호스트 환경을 염두에 두고 작성됨

FROM python:3.11-slim

WORKDIR /app

# 한글 폰트 (matplotlib 축 라벨/범례 깨짐 방지 - vm-03에서도 동일 이슈로 설치했던 패키지)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8501

# 컨테이너 헬스체크 (docker-compose의 depends_on condition에서 활용)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
