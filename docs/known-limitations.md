# Known Limitations & Operating Boundaries

This document provides a transparent, truthful accounting of the current operational boundaries and architectural limitations of HNA / HINA.

---

## 1. Local Desktop Automation vs. Cloud Architecture

### Boundary
- **Cloud Limitation**: The cloud backend running on Render or Docker resides in an isolated Linux container. It **cannot** directly control or interact with a user's local Windows, macOS, or Linux computer when that computer is disconnected, asleep, or lacks an active local companion agent.
- **Dry-Run Status**: The `computer_operator.py` engine defaults to `dry_run=True`. While execution plans, coordinate calculations, and security boundary assertions are fully implemented and verified, actual OS input injection (mouse clicks, key strokes) requires an authenticated, locally running companion daemon with OS accessibility permissions.

---

## 2. Multi-Modal Video Generation

### Boundary
- **Status**: `UNAVAILABLE` in the production pipeline.
- **Rationale**: The agent supports image generation via external image synthesis tools, but video generation (e.g. OpenAI Sora, Google Veo, Runway Gen-3) is not connected to a live production endpoint. Prompting for video creation will explain this limitation rather than fabricating video generation execution.

---

## 3. Render Free Tier Latency & Cold Starts

### Boundary
- **Cold Start Latency**: On Render's free compute tier, backend web services spin down after 15 minutes of inactivity. The initial incoming request after idle can experience a cold-start delay of **30 to 55 seconds** before the container begins accepting HTTP traffic.
- **Mitigation**: Upgrading to a Render Starter/Standard paid compute instance ($7/month) keeps the service warm 24/7 with zero spin-down latency.

---

## 4. Live Third-Party Provider Credentials

### Boundary
- **Status**: `BLOCKED` in local or staging environments without provisioned API keys.
- **Affected Services**: Calling live frontier models (Google Gemini 2.5, Anthropic Claude 3.7 Sonnet, OpenAI GPT-4o, ElevenLabs Neural TTS) requires valid, funded API keys configured in the backend environment.
- **Behavior Without Keys**: The agent safely falls back to local/mock harness execution (`hinaa-mock-v1`) or informs the user of missing configuration rather than producing synthetic hallucinated outputs.

---

## 5. WebRTC Hardware Acoustic Testing

### Boundary
- **Status**: Unit tests for the WebRTC protocol, signaling, and audio state machines pass completely in automated environments. However, real-world acoustic echo cancellation (AEC), microphone background noise rejection, and live conversational barge-in depend on the physical hardware (microphone quality, room acoustics, speaker volume) of the user's client device.

---

## 6. Database Concurrency & Storage Scalability

### Boundary
- **Local SQLite**: The repository supports local SQLite for single-developer velocity. However, SQLite does not support high-concurrency writes across distributed replicas and will experience database lock contention (`database is locked`) under parallel load.
- **Production Standard**: Production deployments must connect to a managed PostgreSQL cluster (configured via `HINAA_DATABASE_URL`).
