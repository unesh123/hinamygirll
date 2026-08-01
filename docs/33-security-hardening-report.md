# 33 — Security hardening report

## Present

- CORS allowlist
- Correlation IDs
- Typed safe errors (no stack traces to clients in HinaaError path)
- Audio size/duration limits
- Realtime frame/buffer/idle limits
- No `VITE_*` secrets pattern
- Prompt injection delimiting + offline corpus
- Privacy endpoints require auth context
- Cross-user memory forget fails closed
- Sensitive memory content blocked
- AssistantTurnPlan `extra=forbid` + empty tools
- Cache-Control: no-store on API responses
- X-Content-Type-Options: nosniff

## Incomplete / blockers for public production

- Full OIDC JWT validation
- PostgreSQL RLS
- WebSocket user binding for private persistence
- Rate limiting middleware (not yet global)
- Dependency audit CI gate automation
- Production CSP headers on frontend host
- Secret scanning in CI
- Staging restore drill
- Disable dev auth in production

## Recommendation

Treat current build as **local/controlled staging candidate scaffolding**, not public production.
