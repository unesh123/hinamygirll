# Observability

The API ships traces (OpenTelemetry), metrics (Prometheus) and error reports (Sentry). Everything is
off or inert by default; tracing costs one boolean check per call site when disabled.

## Run the local stack

```bash
cp infra/observability/prometheus/metrics_token.example infra/observability/prometheus/metrics_token
# put the same value in HINAA_METRICS_TOKEN for the API (Prometheus scrapes /metrics with it)
docker compose -f compose.observability.yaml up -d

HINAA_OTEL_ENABLED=true \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
HINAA_METRICS_TOKEN=<same token> \
  uvicorn hinaa_api.main:app --factory --port 8000   # from apps/api
```

| UI | URL | What you see |
| --- | --- | --- |
| Jaeger | http://localhost:16686 | Request traces: `hinaa-api` service, nested `invoke_agent` → `chat <model>` / `execute_tool <name>` spans, outbound httpx and SQL child spans |
| Grafana | http://localhost:3001 (anonymous viewer; admin/admin) | Dashboard **HINAA API — Requests, LLM & Tools**: request rate/latency/5xx, LLM latency and tokens by model, tool calls by name/outcome |
| Prometheus | http://localhost:9090 | Raw `hinaa_*` series |

Config lives in `infra/observability/` (collector → Jaeger pipeline, Prometheus scrape job, Grafana
provisioning and dashboard JSON). Image tags are pinned in `compose.observability.yaml`.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `HINAA_OTEL_ENABLED` | `false` | Enable tracing (FastAPI, httpx, SQLAlchemy instrumentation) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OTLP/HTTP endpoint; required when tracing is enabled, otherwise tracing is skipped with a warning |
| `OTEL_SERVICE_NAME` | `hinaa-api` | `service.name` resource attribute (`service.version` and `deployment.environment.name` come from the app version and `ENVIRONMENT`) |
| `HINAA_OTEL_SAMPLER_RATIO` | `1.0` | Parent-based trace-id ratio sampler (0–1) |
| `HINAA_OTEL_CAPTURE_CONTENT` | `false` | Opt in to prompt/response/tool arguments/results on spans. Off by default; never enable where prompts contain sensitive data |
| `HINAA_METRICS_TOKEN` | unset | Bearer token for `/metrics` (loopback needs none) |
| `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE` | unset / `0` | Sentry error reporting |

## Traces and logs

- The server span's trace id is returned as `X-Trace-Id` and written to every JSON log line
  (`trace_id`, `span_id`) and Sentry event tag, so a log line, an error and a trace correlate.
  An incoming W3C `traceparent` is honoured; outbound httpx calls carry `traceparent`.
- Spans follow the OpenTelemetry GenAI semantic conventions:
  [client inference spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/client-inference.md)
  (`chat {model}`, `gen_ai.provider.name=anthropic`, request/response model, input/output/cache token
  usage, finish reasons, `error.type`) and
  [execute-tool spans](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/execute-tool.md)
  (`execute_tool {name}`, `gen_ai.tool.name`, `gen_ai.tool.call.id`), nested under an `invoke_agent hina`
  span. Tool spans also carry `hinaa.tool.outcome` and `hinaa.tool.duration_ms`.
  The GenAI conventions are still evolving; attribute names track the upstream repo's `main`.
- `/healthz`, `/readyz` and `/metrics` are not traced.

## Metrics (`/metrics`)

`hinaa_llm_request_duration_seconds{provider,model}`, `hinaa_llm_requests_total{provider,model,outcome}`,
`hinaa_llm_tokens_total{provider,model,type}`, `hinaa_tool_calls_total{tool,outcome}`,
`hinaa_tool_duration_seconds{tool}`, plus the existing `hinaa_http_*` series. Tool names not in the
registry collapse to `unknown` to bound label cardinality.

## Sentry

`init_sentry` sets `send_default_pii=false`, no request bodies, no local variables, and a `before_send`
scrubber that removes cookies/request data, reduces `user` to its id, and redacts any key matching
authorization/cookie/api-key/token/secret/password/session plus bearer tokens and `sk-…` style keys in values.

## Health

- `GET /healthz` — liveness. Constant response; no DB or provider calls.
- `GET /readyz` (alias `/health/ready`) — readiness. Checks required provider configuration, a
  `SELECT 1` against the database and that no `schema_migrations` entries are pending (when persistence is
  enabled). Returns 503 with the failing `database` / `missingConfiguration` detail.
- `GET /health` still mirrors `/readyz`.
