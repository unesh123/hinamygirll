# 64: ElevenLabs Streaming TTS Architecture

## 1. Overview
Specifies mode A (HTTP chunked streaming) and mode B (WebSocket streaming input) for ElevenLabs Text-to-Speech.

## 2. Model Policy
- Fast Route: `eleven_flash_v2_5` (lowest latency)
- Expressive / Nepali Route: `eleven_multilingual_v2` / `eleven_v3` (documented Nepali support)
