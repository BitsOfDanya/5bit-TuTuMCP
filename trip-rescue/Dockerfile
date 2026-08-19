FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8020
ENV PREFERENCE_STORE_PATH=/data/preferences.json

WORKDIR /app


# ------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------

COPY requirements.lock.txt /app/requirements.lock.txt

RUN python -m pip install \
    --no-cache-dir \
    --upgrade pip \
    && python -m pip install \
    --no-cache-dir \
    -r /app/requirements.lock.txt


# ------------------------------------------------------------
# Application
# ------------------------------------------------------------

COPY app /app/app
COPY scripts /app/scripts


# ------------------------------------------------------------
# Runtime persistent data
# ------------------------------------------------------------

RUN mkdir -p /data

VOLUME ["/data"]


# ------------------------------------------------------------
# API
# ------------------------------------------------------------

EXPOSE 8020


# ------------------------------------------------------------
# Container health
# ------------------------------------------------------------

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=10s \
    --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8020/health', timeout=3)" || exit 1


# ------------------------------------------------------------
# Start
# ------------------------------------------------------------

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8020}"]