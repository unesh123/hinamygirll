# 48 — Mobile local live testing

## Scope

Trusted **local-network developer** testing before any public deployment.
Not UpCloud. Not production security.

## Prerequisites

- Owner machine runs API with secrets only in ignored `apps/api/.env.local`
- Optional trusted HTTPS certs under `.cert/` (manual trust; no silent root install)
- Phone and PC on the same private LAN
- Configure `HINAA_ALLOWED_ORIGINS` to include the phone origin
- Optional `HINAA_LAN_IP` if auto-detection is wrong

## Start / stop

```powershell
# Loopback first
powershell -File scripts/start-mobile-local.ps1

# Opt-in LAN bind (trusted network only)
powershell -File scripts/start-mobile-local.ps1 -Lan

# HTTPS when certs exist
powershell -File scripts/start-mobile-local.ps1 -Lan -Https

# Stop recorded processes
powershell -File scripts/start-mobile-local.ps1 -Stop
```

Under HTTPS pages, WebSocket must use `wss:`.

## Firewall guidance

- Prefer private/trusted network profile only.
- Allow inbound TCP 5173 (web) and 8000 (API) only if phone must reach the PC.
- Do not expose database ports.
- Do not open WAN/router ports for this workflow.
- Do not auto-create public tunnels.

## Manual checklist

- [ ] Page loads on phone
- [ ] PWA shell renders
- [ ] Microphone permission prompt works
- [ ] Clear listening indicator
- [ ] Automatic turn detection
- [ ] Partial transcript
- [ ] Final transcript
- [ ] Text streaming
- [ ] First audio playback
- [ ] Avatar jaw movement (amplitude)
- [ ] Avatar expression
- [ ] User interruption
- [ ] Reconnection
- [ ] English / Nepali / Romanized Nepali / Hindi / mixed
- [ ] Pause / resume / end session
- [ ] Text fallback
- [ ] Reduced motion
- [ ] Screen-lock behavior observed (do not claim without testing)

## Auth warning

`HINAA_AUTH_MODE=dev` header auth is **not** production OIDC/RLS. LAN exposure
is developer-only and opt-in.
