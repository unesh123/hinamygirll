# HINAA keys and resources

Never paste secret values into chat, Git, `apps/web`, a `VITE_*` variable, screenshots, or issue reports. Put backend secrets only in `apps/api/.env.local` or a production secret manager.

## Minimum local setup

These are enough to run the UI and deterministic testing:

- Node.js 20+, pnpm, and Python 3.11+.
- `HINAA_PROVIDER_MODE=mock`.
- File-backed SQLite via `HINAA_DATABASE_URL=sqlite+pysqlite:///./.runtime/hinaa.db`.
- A browser with WebGL and microphone permission for avatar and voice UI testing.
- A licensed VRM asset in `apps/web/public/models/` (or the procedural fallback).

## Recommended intelligence stack

| Capability | Backend variable(s) | Required for |
| --- | --- | --- |
| Gemini brain | `GEMINI_API_KEY`, optional `GEMINI_MODEL` | Cloud chat, planning, multimodal fallback |
| OpenAI brain | `OPENAI_API_KEY`, `OPENAI_MODEL` | OpenAI chat route |
| Private premium gateway | `OPENAI_CODEX_API_KEY`, `OPENAI_CODEX_BASE_URL`, `OPENAI_CODEX_MODEL` | Custom/CX model route |
| Anthropic | `HINAA_CLAUDE_API_KEY`, `HINAA_CLAUDE_BASE_URL`, `HINAA_CLAUDE_MODEL` | Claude route |
| Qwen | `HINAA_QWEN_API_KEY`, `HINAA_QWEN_BASE_URL`, `HINAA_QWEN_MODEL` | Multilingual/coding route |
| Groq | `GROQ_API_KEY`, `GROQ_MODEL` | Fast text fallback |
| Live web research | `YDC_API_KEY` | Fresh search, extraction, citations |

You only need one configured cloud brain for chat. Multiple brains improve fallback and model selection; they do not automatically make responses frontier-quality.

## Voice resources

- Azure Speech: `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, plus configured `ne-NP`, `hi-IN`, and English voices. This is the baseline multilingual route.
- ElevenLabs: `ELEVENLABS_API_KEY`, voice IDs, and model IDs for expressive streaming TTS/STT.
- Fish Audio: `FISH_AUDIO_API_KEY` and voice IDs for an optional multilingual route.
- A real microphone, headphones/speakers, HTTPS on mobile, and native-speaker acceptance recordings. A key alone cannot prove uninterrupted voice, barge-in, or lip-sync quality.
- A licensed consenting voice actor or approved custom-voice dataset is required for an original HINAA voice.

## Image and document resources

- Freepik: `FREEPIK_API_KEY` for cloud image generation/editing when your account enables those endpoints.
- Magnific: `MAGNIFIC_API_KEY` for upscale/relight workflows.
- OpenAI-compatible image gateway: `OPENAI_CODEX_API_KEY` + `OPENAI_CODEX_BASE_URL` when available.
- Local image generation: ComfyUI at `HINAA_COMFYUI_BASE_URL` (default `http://127.0.0.1:8188`), a compatible workflow, and a GPU with enough VRAM.
- Persistent object storage (S3/R2/Blob) is required for production image/PDF artifacts; local `apps/api/data/` is development-only.
- PDF generation needs the server document runtime and a durable artifact store; progress UI is only truthful when jobs emit step events.

## Agent, desktop, and integrations

- `TINYFISH_API_KEY` is optional for goal-based web-agent tasks.
- `GAMMA_AI_API_KEY` is optional for slide generation.
- GitHub OAuth App credentials (client ID/secret, callback URL, encrypted refresh tokens, repository allowlist) are required before HINAA can safely modify repositories.
- MCP servers need an explicit per-server URL/command, authentication method, tool allowlist, timeout, and audit log. There is no universal MCP key.
- Desktop control requires a local authenticated bridge, explicit user approval for mutations, and an action receipt/rollback strategy.

## Production infrastructure

- Vercel is suitable for the static/PWA frontend. Run the FastAPI WebSocket/API service separately on a long-lived HTTPS host; do not put private provider keys in Vercel client variables.
- Use Clerk or another OIDC provider with server-side JWT verification and an owner allowlist.
- Use managed PostgreSQL (optionally pgvector), private object storage, encrypted secret management, backups, restore drills, rate limits, monitoring, error tracking, and rollback deployments.
- Set exact `HINAA_ALLOWED_ORIGINS` to the deployed frontend origin and require HTTPS/WSS.
- For owner-only access, use an allowlisted account/subject and keep the service stopped or unreachable when you are not using it. A public URL that is merely “not advertised” is not private.

## Acceptance gates before calling it launch-ready

1. Provider health and model selection succeed with real keys and graceful fallback when each provider is unavailable.
2. Image generation succeeds with and without ComfyUI, and reference-image behavior is tested against the chosen provider’s actual edit API.
3. Voice survives reconnects, barge-in, tab sleep, mobile permission changes, and all three language policies.
4. VRM loading, switching, full-body framing, expressions, hands, and lip-sync are inspected on the target desktop and phone.
5. GitHub/MCP/desktop actions enforce owner identity, approval, timeout, cancellation, idempotency, and audit receipts.
6. Backups, restore, monitoring, quotas, HTTPS/WSS, and secret rotation are exercised in staging.

The complete current implementation status is in [CURRENT-STATUS.md](CURRENT-STATUS.md) and the release gates are in [HINAA-RELEASE-EVIDENCE.md](HINAA-RELEASE-EVIDENCE.md).
