# 35 — UpCloud staging architecture (planned)

```text
Browser PWA
  → HTTPS reverse proxy
  → FastAPI (REST + /v1/realtime WebSocket)
  → Gemini + Azure (real mode only)
  → PostgreSQL (managed preferred)
```

## Authorization

Provisioning requires:

```text
HINAA_ALLOW_UPCLOUD_PROVISIONING=1
HINAA_UPCLOUD_PROVISIONING_CONFIRM=I_AUTHORIZE_STAGING_RESOURCES
```

**Status: not authorized; no resources created.**

## Suggested minimal staging

- One Cloud Server
- Reverse proxy with WebSocket upgrade
- Managed PostgreSQL if available; else documented single-node Postgres for staging only
- Firewall: 22 (admin), 80/443
- Tags: `project=hinaa`, `env=staging`

## Explicit non-goals until measured need

Kubernetes, GPU, multiple load-balanced app nodes, public database ports.
