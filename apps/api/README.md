# HINAA API — Phase 3

FastAPI modular monolith for the versioned realtime gateway plus the preserved record-then-process cascade. Mock mode is the default and makes no provider calls. Real mode is explicit per session/request and requires backend-only configuration in ignored `.env.local`.

Tier A conversation brain: layered prompt assembly lives in `hinaa_api/prompts/` and is shared by REST and realtime paths. See `docs/26-tier-a-conversation-brain-implementation.md`.

```powershell
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements-dev.txt
apps/api/.venv/Scripts/python.exe -m uvicorn hinaa_api.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/health/ready`. `/v1/realtime` accepts versioned JSON control messages and bounded 16 kHz PCM-S16LE binary frames. Audio is held only for the active in-memory turn and discarded on commit, interruption, limit, timeout, or disconnect. The Phase 2 PCM WAV endpoints remain the fallback.
