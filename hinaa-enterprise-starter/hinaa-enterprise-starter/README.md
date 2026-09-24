# HINAA Enterprise Starter

A runnable reference implementation matching the supplied pink/white HINAA UI direction. Included: streaming text chat, OpenAI Realtime WebRTC voice, a Three.js GLB avatar stage, local workspace API with path-traversal protection, navigation shell, Docker build, health endpoint, image/library placeholders, and environment template.

## Run

```bash
cp .env.example .env.local
# add OPENAI_API_KEY
# place your licensed VRM/GLB model at public/avatar.glb
npm install
npm run dev
```

Open `http://localhost:3000`.

## Required credentials

Core development: `OPENAI_API_KEY`. Multi-user production: Supabase URL, publishable/anon key, and a server-only service role key. Optional keys are listed in `.env.example`. Do not put secret keys in browser code.

## Important production gaps

This starter is not a complete enterprise deployment. Before a public launch add real authentication, RLS policies, tenant isolation, object storage, malware scanning, moderation, rate limits, Redis/job queues, provider fallbacks, observability, billing ledger, backups, regional deployment, load testing, CSP, CSRF protection, secret management, and legal review. Never use the local workspace endpoint as shared production storage on serverless hosting.

## Avatar

`AvatarStage` loads `/public/avatar.glb`. Replace the filename or loader if your asset is VRM. Lip movement uses a best-effort `aa` morph target. Production avatars should map phoneme/viseme events to the model's actual morph-target dictionary and blend eye blinks, gaze, idle motion, and interruption state.

## API routes

- `POST /api/chat`: streams response text
- `POST /api/realtime/token`: returns a short-lived browser-safe Realtime credential
- `GET/POST /api/workspace`: sandboxed local project directory
- `GET /api/health`: health probe

## Scaling reference

Place a CDN/WAF before the app. Keep stateless web instances behind autoscaling. Put jobs in a durable queue. Cache only safe, tenant-scoped retrieval results. Store files in object storage. Use Postgres for metadata, pgvector or managed retrieval for RAG, Redis only for ephemeral state, and an isolated container service for code execution. Set per-tenant quotas and circuit breakers for every AI provider.
