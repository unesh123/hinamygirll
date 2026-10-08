FROM python:3.12-slim AS api

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates libasound2 \
    && rm -rf /var/lib/apt/lists/*
COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

# Copy source explicitly, never the developer's API directory or environment.
COPY apps/api/hinaa_api /app/hinaa_api
COPY scripts/start-api-container.py /app/start-api-container.py
RUN useradd --create-home --uid 10001 hina \
    && mkdir -p /app/data /app/.hina /app/hinaa_api/data /home/hina/.hinaa /home/hina/.hina \
    && chown -R hina:hina /app/data /app/.hina /app/hinaa_api/data /home/hina
USER hina
ENV HOME=/home/hina ENVIRONMENT=production HINAA_AUTH_MODE=clerk \
    HINAA_PROVIDER_MODE=agent-router HINAA_PERSISTENCE_ENABLED=true \
    HINAA_ALLOW_REMOTE_LOCAL_TOOLS=false HINAA_ALLOW_TUNNEL_DEV_AUTH=false
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:${PORT}/health/live || exit 1
CMD ["python", "/app/start-api-container.py"]
