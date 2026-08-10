# 66: Mobile Echo Cancellation & Genuine Barge-In

## 1. Microphone Constraints
- `echoCancellation: true`
- `noiseSuppression: true`
- `autoGainControl: true`

## 2. PlaybackLeakGuard
- Compares microphone audio energy envelope against active speaker output envelope.
- Prevents HINAA from transcribing its own speaker output or replying to itself.
- Instantly aborts playback and cancels server generation on confirmed user barge-in.
