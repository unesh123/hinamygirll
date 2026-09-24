# Known Limitations & Hardware Prerequisites

**Last Updated:** September 3, 2026

---

## 1. Local Voice & VAD Constraints
- **Whisper Latency on CPU:** Running `FasterWhisperService` with `int8` quantization on Windows without CUDA GPU takes 1.5–3.0s per chunk. Push-to-Talk provides a guaranteed commit mechanism when continuous VAD is ambiguous in noisy rooms.
- **Microphone Automatic Gain Control (AGC):** Browser AGC in noisy rooms can amplify laptop fan noise above 0.035 RMS. The noise floor clamp (`<= 0.022`) prevents lockup, but headset microphones or low-noise environments remain recommended for optimal continuous hands-free operation.

## 2. Image Studio & Local Models
- **ComfyUI Requirement:** Local image generation requires an active ComfyUI instance on `http://127.0.0.1:8188` with SDXL/SD1.5 checkpoints loaded. When unavailable, Image Studio clearly displays the offline status and allows web image search reference instead.
- **Sequential Queue:** Local generation slots run sequentially to avoid VRAM OOM on consumer GPUs.

## 3. Cloud Provider Quotas
- **CX Gateway Limits:** Upstream Cloudflare-tunneled CX endpoints can experience intermittent rate limits or quota depletion. The companion controller automatically falls back to Gemini 2.5 Flash with user-visible notification.
- **Gamma AI Tooling:** Gamma presentations require an active, valid API key in `apps/api/.env.local`. Test tokens must never be logged or committed.
