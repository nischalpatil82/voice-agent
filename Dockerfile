FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5004 \
    VOICE_AGENT_PRODUCTION=true

WORKDIR /app

# Runtime packages only.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       g++ \
       portaudio19-dev \
       ffmpeg \
       libportaudio2 \
       curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc g++ portaudio19-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5004

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/ready" || exit 1

# Uses the hardened Waitress path in server.py.
CMD ["sh", "-c", "python server.py --project justbill --port ${PORT} --production"]
