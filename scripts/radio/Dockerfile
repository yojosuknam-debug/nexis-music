FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir boto3==1.35.99
# 코드는 이미지에 굽지 않고 레포를 읽기전용으로 붙인다 → git pull + restart 로 갱신
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
CMD ["python", "/app/scripts/radio/streamer.py"]
