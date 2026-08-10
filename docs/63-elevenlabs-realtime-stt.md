# 63: ElevenLabs Scribe v2 Realtime STT Integration Architecture

## 1. Overview
This document specifies the server-side integration of ElevenLabs Scribe v2 Realtime Speech-to-Text (STT) for live multilingual speech recognition (Nepali, Hindi, English).

## 2. Event Model & Sequence Tracking
All STT events strictly maintain monotonicity, session isolation, and script preservation:
- `stt.session.ready`
- `stt.partial`
- `stt.final`
- `stt.error`
- `stt.closed`
- `speech.started`
- `speech.ended`

Each event carries `sessionId`, `generationId`, `sequenceId`, `timestamp`, `isFinal`, and `language`.

## 3. Filtering & Unicode Preservation
- Unicode Devanagari (Nepali/Hindi) and Romanized scripts are preserved verbatim.
- Empty final transcripts are rejected.
- Duplicate consecutive final transcripts are suppressed.
