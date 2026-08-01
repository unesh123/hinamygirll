# Multi-stage API image example. Do not bake secrets.
FROM python:3.14-slim AS api
WORKDIR /app
COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api /app
ENV HINAA_PROVIDER_MODE=mock
USER nobody
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')"
CMD ["uvicorn", "hinaa_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
