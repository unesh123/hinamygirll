# HINAA (SAKURA OS) — MASTER AI SYSTEM SPECIFICATION & CURRENT STATUS
**Target Audience:** Share this document directly with ChatGPT, Claude, Gemini, or any collaborating AI assistant working on the HINAA codebase. It reflects 100% verified architectural truth, active configurations, working endpoints, and test status.

---

## 1. Executive Summary & Core Identity

- **Name / Persona:** **HINAA** (Sakura OS AI Companion & Copilot).
- **Core Experience:** Multimodal companion blending real-time voice conversations (ElevenLabs / Web Speech), 3D VRM expressive avatar animations (Three.js), persistent cross-session memory, multi-provider reasoning brains (Gemini, Claude via OpenRouter, OpenAI), and high-resolution creative generation (Magnific / Freepik Suite).
- **Project Structure (Monorepo):**
  - `apps/web`: React 19 + TypeScript + Vite + TailwindCSS v4 + Three.js / `@pixiv/three-vrm`.
  - `apps/api`: Python 3.14 + FastAPI + Pydantic v2 + SQLAlchemy + Uvicorn (`127.0.0.1:8000`).
  - `packages/contracts`: Shared JSON schemas for companion turns, tool requests, and live messaging.

---

## 2. Active System Status & Verification Matrix

| Component | Status | Verification & Notes |
| :--- | :--- | :--- |
| **Brain Provider Mode** | `real` (Active) | Primary: `gemini-3.5-flash-lite` (direct API). Secondary: Claude via OpenRouter (`anthropic/claude-3-haiku` / `claude-3.5-sonnet`). |
| **Voice / Speech Synthesis** | `operational` | ElevenLabs streaming TTS (`eleven_multilingual_v2` / `eleven_flash_v2_5`) with Web Speech API browser fallback. |
| **Voice Interruption (Barge-In)**| `operational` | **Latency ~60ms.** Threshold lowered to `0.045` RMS (`bargeInFrames: 3`, voice floor `0.040`). `Escape` key & interactive Stop button halt speech immediately. |
| **3D VRM Avatar** | `operational` | 5 models registered in `apps/web/public/models/`. Normalized blendshapes, real-time audio viseme lip-sync (`A, I, U, E, O`), and VMC motion bridge (UDP `39539`/`64310`). |
| **Magnific / Freepik Suite** | `operational` | Active API key verified. Generating live 1024x1024+ art. Omitted invalid `model: flux-schnell` parameter. Served locally at `/v1/generated-images/{filename}`. |
| **Video Generation** | `disabled` | Strict HTTP 403 `VIDEO_GENERATION_FORBIDDEN` enforced across all backend layers per safety policy. |
| **Memory & Conversations** | `operational` | SQLite database at `~/.hinaa/hinaa.db`. CRUD endpoints `/v1/conversations` (list, messages, title update) and automatic memory extraction (`memoryCandidates`). |
| **Frontend Tests & Build** | `100% PASS` | `vitest`: 45 test files, 260 tests passed. `tsc -b && vite build` completed in ~9.4s. |
| **Backend Tests** | `100% PASS` | `pytest apps/api/tests/test_tool_dispatch.py`: 7/7 passed. |

---

## 3. Architecture Deep Dive

### 3.1 LLM Gateway & Brain Orchestration
- **Location:** `apps/api/hinaa_api/services.py`, `providers/`, `prompts/`.
- **Stream Turn Endpoint:** `POST /v1/conversations/turns:stream`
  - Yields streaming SSE events: `step`, `chunk`, `plan`, `toolRequests`, `final`.
  - Structured output schema: `spokenText`, `displayText`, `toolRequests`, `performance` (face presets, gestures, head motion), `emotion`, `memoryCandidates`.
- **Parameter Normalization:**
  - Standardized in `models.py` (`ToolRequest`, `ToolExecutionRequest`). Supports aliases `toolName`/`tool`/`name` and `parameters`/`arguments`/`args`/`params`.
  - Normalizes tool aliases (e.g. `description`, `text`, `query`, `prompt_text` -> `prompt`).
- **Safety & Standing Consent:**
  - Tools with standing consent (`magnific_image_generate`, `freepik_image_generate`, `image_search`, `web_search`) execute immediately without user confirmation prompt blocks (no 409).
  - Enforces server-resolved `userId` preventing client parameter injection.

### 3.2 Voice, Turn-Taking & Lip-Sync Pipeline
- **Controllers:**
  - `apps/web/src/features/audio/turnTakingController.ts`: Evaluates mic input against dynamic audio energy thresholds.
  - `apps/web/src/features/audio/useLiveConversation.ts`: Coordinates microphone stream, silence detection, turn completion, and playback interruptions.
- **Barge-In Sensitivity:**
  - `speakerThreshold`: `0.045` RMS.
  - `bargeInFrames`: `3` frames (~60ms at 50 FPS).
  - Dynamic Voice Floor: `Math.max(0.045, (speakerThreshold || 0.045) * 1.5)`.
  - On barge-in: calls `audioPlayback.stop()`, `live.stop()`, `window.speechSynthesis.cancel()`, and aborts in-flight turn requests.
- **Lip-Sync & Expression Pipeline:**
  - `apps/web/src/features/avatar/VRMAvatar.tsx`: Web Audio `AnalyserNode` reads frequency bands during speech.
  - Formant analysis maps spectrum to Japanese vowel blendshapes: `aa`, `ih`, `ou`, `ee`, `oh`.
  - Applies micro-blinks, gaze tracking towards camera, and head idle motion.

### 3.3 3D VRM Model Suite
- **Location:** `apps/web/public/models/`
- **Available Models:**
  1. `5798998195377315936 (1).vrm` — Hinaa (Original) with pink ribbons and cat ears (Default).
  2. `hinaa.vrm` — Hinaa Classic VRoid avatar.
  3. `AvatarSample_E.vrm` — Sakura Student (Sample E), lightweight geometry.
  4. `model_5447.vrm` — Hinaa Casual streetwear avatar.
  5. `model_6164.vrm` — Hinaa Kimono festive avatar.
- **VMC Bridge:** UDP listener running in background on port `39539` / `64310` to receive external motion capture data (Warudo, VSeeFace, mocopi).

### 3.4 Image Generation & Serving Fabric
- **Location:** `apps/api/hinaa_api/tools/freepik_suite.py`, `cloud_image.py`, `main.py`.
- **Tools:**
  - `magnific_image_generate`: Direct text-to-image with Freepik high-res engine.
  - `freepik_image_generate`: High-resolution generation.
  - `magnific_upscale`: Image enhancement & upscaling.
  - `freepik_stock_search`: Stock image search and download.
- **Serving Path:**
  - Generated images save to `apps/api/data/images/{filename}`.
  - HTTP endpoints: `GET /v1/generated-images/{filename}` and `GET /api/v1/generated-images/{filename}` (traversal-safe).
  - Chat rendering: `apps/web/src/features/chat/components/GenericResultRenderer.tsx` handles both string URLs and `{ url, file_path }` object arrays.

### 3.5 Persistence & Memory Layer
- **Location:** `apps/api/hinaa_api/persistence/`
- **Database:** SQLite via SQLAlchemy (`C:\Users\unesh\.hinaa\hinaa.db`).
- **REST Endpoints:**
  - `GET /v1/conversations`: Returns recent conversation threads, message counts, and previews.
  - `GET /v1/conversations/{id}/messages`: Returns full message history.
  - `PATCH /v1/conversations/{id}`: Rename conversation title.
- **Auto-Memory:** `memoryCandidates` emitted by the LLM (preferences, user facts) are automatically extracted and saved to the memory store without manual user intervention.

---

## 4. Key Configuration Keys (`apps/api/.env.local`)

```ini
# Core Mode
HINAA_PROVIDER_MODE=real
HINAA_AUTH_MODE=dev
HINAA_DEV_AUTH_SUBJECT=local-dev-user
HINAA_DATABASE_URL=sqlite+pysqlite:///C:/Users/unesh/.hinaa/hinaa.db

# Brain: Google Gemini
GEMINI_API_KEY=***
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_PLANNER_MODEL=gemini-3.5-flash-lite

# Brain: OpenRouter / Claude
ANTHROPIC_API_KEY=***
HINAA_CLAUDE_BASE_URL=https://openrouter.ai/api/v1
HINAA_CLAUDE_MODEL=anthropic/claude-3-haiku
HINAA_CLAUDE_PROTOCOL=openai-compatible

# Voice: ElevenLabs
ELEVENLABS_API_KEY=***
ELEVENLABS_VOICE_ID=TRnaQb7q41oL7sV0w6Bu
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_TTS_MODEL_FAST=eleven_flash_v2_5

# Image: Freepik & Magnific AI Suite
FREEPIK_API_KEY=***
MAGNIFIC_API_KEY=***
MAGNIFIC_MONTHLY_PLAN_CREDITS=45000
MAGNIFIC_VIDEO_GENERATION_ENABLED=false
```

---

## 5. Instructions for Collaborating AI / Next Steps

When picking up development or adding new features to HINAA:
1. **Never Re-introduce Video Generation:** Project policy strictly forbids video generation.
2. **Preserve Tool Schema Aliases:** LLMs output tool calls with keys `name` and `args`. Maintain the alias support in `models.py` and `prompts/fallback.py`.
3. **Preserve Low Barge-In Threshold:** Keep voice barge-in frames <= 3 and RMS <= 0.045 in `turnTakingController.ts` so interruption feels responsive.
4. **Running Commands:**
   - **Frontend:** Run `pnpm --dir apps/web dev` or `npm --prefix apps/web run dev` (runs on `http://localhost:5173`).
   - **Backend:** Run `& "apps/api/.venv/Scripts/python.exe" -m uvicorn hinaa_api.main:app --app-dir apps/api --host 127.0.0.1 --port 8000`.
   - **Tests:** Run `npm --prefix apps/web run test` and `pytest apps/api/tests/test_tool_dispatch.py`.