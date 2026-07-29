# HINAA API — Phase 2

FastAPI modular monolith for the record-then-process cascade. Mock mode is the default and makes no provider calls. Real mode is explicit per request and requires backend-only configuration in ignored `.env.local`.

```powershell
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python.exe -m pip install -r apps/api/requirements-dev.txt
apps/api/.venv/Scripts/python.exe -m uvicorn hinaa_api.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/health/ready`. Raw microphone audio is accepted only as 16 kHz, 16-bit, mono PCM WAV, capped at 20 seconds and 4 MiB, held in memory for the request, and not retained.

