# HINAA OS — Phase 09: Creative Studio Runbook & Operations

## 1. Local Runtime Operations

### Health & Capability Discovery
Check active creative engine status and discovered hardware:
```bash
curl http://127.0.0.1:8000/api/creative/capabilities
```
Expected output:
```json
{
  "gpu_name": "NVIDIA GeForce RTX 4060 Laptop GPU",
  "vram_total_mb": 8188,
  "vram_free_mb": 4851,
  "ffmpeg_available": true,
  "comfyui_available": false,
  "capabilities": {
    "TEXT_TO_IMAGE": { "status": "AVAILABLE", "provider": "local_engine" },
    "INPAINT": { "status": "AVAILABLE", "provider": "local_engine" },
    "TIMELINE_EXPORT": { "status": "AVAILABLE", "provider": "ffmpeg_exporter" },
    "TEXT_TO_VIDEO": { "status": "BLOCKED", "provider": "none" }
  }
}
```

---

## 2. Enabling Neural Video / ComfyUI Models

To activate generative video (T2V/I2V) or local diffusion checkpoints:
1. Start the local ComfyUI instance on port 8188:
   ```bash
   cd C:\ComfyUI
   .\venv\Scripts\python.exe main.py --port 8188 --listen 127.0.0.1
   ```
2. Download desired diffusion checkpoints into `C:\ComfyUI\models\checkpoints` (e.g. `svd_xt.safetensors` for video or `sd_xl_turbo_1.0_fp16.safetensors` for high-speed images).
3. The next call to `/api/creative/capabilities` will automatically discover ComfyUI as online and update the operational matrix.

---

## 3. Maintenance, Cleanup & Recovery

### Intermediate File Cleanup
All temporary frames from timeline video rendering are isolated within OS temporary directories (`hinaa_timeline_*`) and purged automatically. If disk space drops below 5 GB, run:
```powershell
Remove-Item -Recurse -Force "$env:TEMP\hinaa_timeline_*" -ErrorAction SilentlyContinue
```

### Stale Job Recovery
If the API restarts while jobs are running:
- `PersistentJobStore` restores job records from `DATA_DIR/creative_jobs.json`.
- In-flight jobs interrupted by shutdown are transitioned to `FAILED` with error code `SERVER_RESTARTED`.
- Clients can issue `POST /api/creative/jobs/{id}/retry` to safely resume execution without double-billing.
