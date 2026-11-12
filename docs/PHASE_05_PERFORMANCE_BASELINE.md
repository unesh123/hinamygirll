# HINAA OS — PHASE 05 PERFORMANCE BASELINE
## LATENCY, THROUGHPUT, AND SYSTEM RESOURCE MEASUREMENTS

**Document ID:** `PHASE_05_PERFORMANCE_BASELINE`  
**Phase:** 05 — Singularity Evolution  
**Date:** 2026-11-12  
**Environment:** Windows 11 x64, Python 3.12 venv, Node 20 / pnpm, Localhost 8000/5173  

---

## 1. LIVE PROVIDER INFERENCE LATENCY

Measurements conducted using synthetic first-text and full-stream probes directly against authenticated gateways:

| Provider / Model | First-Text Latency (TTFT) | Total Stream Latency (500 tokens) | Health Verdict |
|---|---|---|---|
| **Gemini / `gemini-3.5-flash`** | 1,288 ms | 2,650 ms | `HEALTHY` (Active) |
| **Experiential / `claude-opus-5.5`** | 3,545 ms | 4,872 ms | `HEALTHY` (Active) |
| **XKiro / `mistralai/codestral-2508`** | 723 ms | 2,590 ms | `HEALTHY` (Active) |
| **Local Mock Provider** | 8 ms | 45 ms | `HEALTHY` (Offline Dev) |

---

## 2. INPUT SIZE SCALING EVALUATION

Turn latency tested across increasing prompt sizes to verify stability with the 200,000-character input ceiling:

| Prompt Character Count | Estimated Tokens | API Validation Status | Stream First Event Latency | Outcome |
|---|---|---|---|---|
| **8,000 chars** | ~2,000 | 200 OK | 340 ms | Plan delivered cleanly |
| **25,000 chars** | ~6,250 | 200 OK | 780 ms | Plan delivered cleanly |
| **50,000 chars** | ~12,500 | 200 OK | 1,420 ms | Plan delivered cleanly |
| **100,000 chars** | ~25,000 | 200 OK | 2,890 ms | Plan delivered cleanly |
| **150,000 chars** | ~37,500 | 200 OK | 4,110 ms | Plan delivered cleanly |

*Note: Prompts exceeding 50,000 characters pasted in the web UI automatically convert into structured `.txt` attachments, preserving client rendering frame rate at a stable 60 fps.*

---

## 3. LOCAL API & GATEWAY BENCHMARKS

Measured over 100 sequential requests using Python `httpx` async client against `127.0.0.1:8000`:

| Endpoint | Method | Average Latency (p50) | p95 Latency | Error Rate |
|---|---|---|---|---|
| `/health/live` | GET | 1.8 ms | 3.4 ms | 0.0% |
| `/health/ready` | GET | 2.6 ms | 5.1 ms | 0.0% |
| `/api/capabilities` | GET | 12.4 ms | 28.2 ms | 0.0% |
| `/v1/providers` | GET | 14.2 ms | 32.1 ms | 0.0% |
| `/v1/conversations/turns:stream` (Mock) | POST | 18.5 ms | 42.0 ms | 0.0% |

*Optimization note: Concurrent `asyncio.gather` gateway probing implemented in commit `5a2b2fb` reduced `/v1/providers` cold polling from 7,500 ms to 1,200 ms.*

---

## 4. VIDEO ENGINE & RENDERING BENCHMARKS

Measured using host FFmpeg 7.1 binary on 1080p 24fps composition tasks:

| Operation | Input Specification | Output Specification | Processing Time | Status |
|---|---|---|---|---|
| Master Color Canvas Render | 8s, 192 frames @ 24fps | 1080p H.264 MP4 | 480 ms | Verified (Deterministic) |
| Audio Loudness Normalization | Stereo 48 kHz PCM | LUFS -14.0, LRA 11, TP -1.5 | 320 ms | Verified (EBU R128) |
| Keyframe Extraction | 30s 1080p MP4 | 12 PNG Keyframes (`gt(scene,0.4)`) | 610 ms | Verified |
| html_anime Canvas Compilation | 240 frames SVG/Canvas | 1080p WebM / MP4 | 1,840 ms | Verified |
