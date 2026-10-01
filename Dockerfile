FROM python:3.12-slim AS api

WORKDIR /app

# Install system dependencies (curl for healthchecks, audio libraries for speech)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

COPY apps/api /app

ENV PYTHONPATH=/app
ENV PORT=8000
ENV HINAA_PROVIDER_MODE=agent-router

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn hinaa_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
