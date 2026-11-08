# Operations runbook

Backend hardening knobs for `apps/api`. Every setting has a safe default; local dev and the test suite need none of them.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `HINAA_LOG_FORMAT` | `text` | `json` emits one JSON object per log line (ts, level, logger, message, request_id, trace_id, user_id, plus extras). |
| `HINAA_ALLOWED_ORIGINS` | localhost:5173, `https://hinaa-workspace.vercel.app` | Comma-separated CORS origin allow-list (existing). |
| `HINAA_CORS_ORIGINS` | empty | Extra origins, merged with the list above. |
| `HINAA_CORS_ORIGIN_REGEX` | `^https://hinaa-workspace(-[a-z0-9-]+)?\.vercel\.app$` | Pattern for preview deployments. Set to an empty string to disable previews. |
| `HINAA_METRICS_TOKEN` | unset | Bearer token for `/metrics`. |
| `HINAA_MAX_BODY_BYTES` | `26214400` (25 MB) | Max request body; larger gets `413`. `0` disables. |
| `HINAA_MAX_UPLOAD_BYTES` | `629145600` (600 MB) | Cap for avatar import and creative asset upload routes. |
| `HINAA_RATE_LIMIT_ENABLED` | auto | Auto = on when `ENVIRONMENT=production` (the Docker image), off otherwise. `true`/`false` overrides. |
| `HINAA_RATE_LIMIT_PER_MINUTE` | `600` | Default bucket per user (or client IP). `0` = unlimited. |
| `HINAA_RATE_LIMIT_EXPENSIVE_PER_MINUTE` | `30` | Stricter bucket for expensive POST routes. |
| `HINAA_TRUST_PROXY` | `false` | Honour the first `X-Forwarded-For` entry for the client IP. Enable only behind a proxy that overwrites the header (Render does). |
| `HINAA_OTEL_ENABLED` / `OTEL_EXPORTER_OTLP_ENDPOINT` | off | Optional OpenTelemetry export, see below. |
| `SENTRY_DSN` | unset | Optional Sentry error reporting, see below. |

## Request IDs and tracing

Every response carries `X-Request-Id` and `X-Trace-Id`. An incoming `X-Request-Id` (1-128 chars of `[A-Za-z0-9._:-]`) or `X-Correlation-ID` is reused, otherwise one is generated. The trace id comes from a valid W3C `traceparent`, then `X-Trace-Id`, else is generated. Both ids are available to every log line via contextvars (`hinaa_api.ops.context`).

Each request writes one `hinaa.access` log line with `method`, `path` (route template when matched), `status`, `duration_ms` and `user_id` when the Clerk auth middleware resolved one. Bodies, headers and tokens are never logged. Health and `/metrics` probes are skipped unless they fail with 5xx.

## Metrics

`GET /metrics` serves Prometheus text format:

- `hinaa_http_requests_total{method,route,status}`
- `hinaa_http_request_duration_seconds` histogram `{method,route}`
- `hinaa_http_requests_in_flight`
- `hinaa_rate_limited_total{bucket}`, `hinaa_body_too_large_total`, `hinaa_process_start_time_seconds`

Labels use route templates, so cardinality stays bounded; unmatched paths collapse to `unmatched`. Metrics are per worker process.

Access: a loopback client without `X-Forwarded-For` is always allowed. Any client sending `Authorization: Bearer $HINAA_METRICS_TOKEN` is allowed. Otherwise the endpoint returns `404` (no token configured) or `401` (token configured). It bypasses Clerk only because the handler enforces this check itself.

Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: hinaa-api
    scheme: https
    metrics_path: /metrics
    authorization:
      credentials_file: /etc/prometheus/hinaa_metrics_token
    static_configs:
      - targets: ["api.example.com"]
```

In Grafana, add the Prometheus data source and chart, for example `sum by (route) (rate(hinaa_http_requests_total[5m]))` and `histogram_quantile(0.95, sum by (le, route) (rate(hinaa_http_request_duration_seconds_bucket[5m])))`.

`/api/telemetry/metrics` (JSON latency report) and `/v1/enterprise/metrics` remain as before; the telemetry routes are exempt from Clerk auth, so prefer `/metrics` for scraping.

## Rate limiting

In-process token bucket, per worker, keyed by authenticated user id, falling back to client IP. Exceeding it returns `429` with `Retry-After` and `X-Request-Id`. Expensive POST routes (conversation and Astra turn streams, creative jobs, vision react/observe, telephony calls, MCP tool calls, browser and coding tasks, speech transcription; with or without the `/api` prefix) share a stricter bucket. Health checks, `/metrics`, CORS preflight and Twilio webhook routes are exempt. Limits are not shared across workers or instances; use an edge limiter for global limits.

## Body size

Requests whose `Content-Length` (or streamed size) exceeds `HINAA_MAX_BODY_BYTES` get `413`. Avatar import and creative asset upload use `HINAA_MAX_UPLOAD_BYTES`. Routes that read uploads still apply their own tighter limits (documents 10 MB, audio 4 MB).

## CORS

Allowed origins are `HINAA_ALLOWED_ORIGINS` plus `HINAA_CORS_ORIGINS`, plus anything matching `HINAA_CORS_ORIGIN_REGEX`. The previous `https://.*\.vercel\.app` wildcard (any Vercel tenant) is gone. Allowed request headers are an explicit list: `Accept`, `Authorization`, `Content-Type`, `X-Request-Id`, `X-Correlation-ID`, `X-Trace-Id`, `traceparent`, `tracestate`, `X-HINAA-Dev-User`, `X-HINAA-PC-Session`, `X-HINAA-Alignment`. Add a header to `CORS_ALLOW_HEADERS` in `hinaa_api/ops/setup.py` when the web client starts sending a new one.

## Sentry (optional)

`sentry-sdk` is not a hard dependency. To enable: `pip install sentry-sdk` in the image, then set `SENTRY_DSN` (and optionally `SENTRY_TRACES_SAMPLE_RATE`). `send_default_pii` is off. Without the package the API logs a warning and continues.

## OpenTelemetry (optional)

Not pinned in `requirements.txt` to keep the image small. To enable, install `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-http`, `opentelemetry-instrumentation-fastapi` and `opentelemetry-instrumentation-httpx`, then set `HINAA_OTEL_ENABLED=true` and `OTEL_EXPORTER_OTLP_ENDPOINT` (and `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_HEADERS` as needed). FastAPI and httpx are then auto-instrumented; health and metrics URLs are excluded. If the packages or endpoint are missing the API warns and starts normally. W3C `traceparent` is propagated and echoed regardless.

## CI

`.github/workflows/security.yml` runs `pip-audit` as a blocking gate, a gitleaks working-tree scan (`.gitleaks.toml` allowlists test fixtures, docs and example env files), and a `docker build` check with `push: false`. `pypdf` was bumped to 6.21.4 to clear the 18 advisories reported against 6.19.0.
