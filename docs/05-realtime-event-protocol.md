# Realtime event protocol

## Purpose

Provide a vendor-neutral, reconnectable contract for voice, text, audio, and avatar performance.

## Decision

Protocol `1.0` uses UTF-8 JSON control events over authenticated WebSocket. Binary audio frames may follow a preceding `user.audio.chunk`/`assistant.audio.chunk` descriptor containing codec, sample rate, channels, byte length, and chunk index. The canonical typed envelope is [realtime-event.schema.json](../packages/contracts/schemas/realtime-event.schema.json).

Required envelope fields are `protocolVersion`, UUID `eventId`, UUID `sessionId`, nullable/required-by-event `turnId`, non-negative `sequence`, RFC 3339 `timestamp`, `type`, typed `payload`, and optional `traceId`. Servers allocate sequence numbers per session. Clients allocate event IDs and monotonically increasing client chunk indexes; the server emits authoritative sequences.

### Event set and direction

| Event | Direction | Key payload |
|---|---|---|
| `session.started` | S→C | capabilities, resume token expiry |
| `microphone.started/stopped` | C→S | codec/config or reason |
| `user.audio.chunk` | C→S | chunk index, format, bytes descriptor |
| `user.transcript.partial/final` | S→C | text, language, stability/confidence |
| `assistant.turn.started` | S→C | provider route, mode |
| `assistant.text.delta/completed` | S→C | delta/full text |
| `assistant.emotion.changed` | S→C | allowlisted emotion |
| `assistant.motion.cue` | S→C | allowlisted face/gesture/gaze/head cue |
| `assistant.viseme.frame` | S→C | relative ms, A/I/U/E/O weights |
| `assistant.audio.chunk/completed` | S→C | format/chunk or duration |
| `assistant.interrupted` | either | reason and last accepted sequence |
| `provider.fallback` | S→C | from/to, reason category, user message |
| `tool.approval.required` | S→C | future-only preview/expiry |
| `error` | S→C | code, retryable, user message, correlation |
| `session.completed` | either | reason |

### Ordering and idempotency

`session.started` precedes turn events. A final transcript precedes `assistant.turn.started`; text deltas precede text completion; audio/viseme frames occur only inside the active turn; audio completion precedes normal turn completion. Receivers keep a bounded event-ID set and ignore duplicates. A lower/equal sequence is duplicate; a gap triggers `GET /v1/sessions/{id}/events?after=N`. Audio chunks are additionally deduplicated by `(turnId, streamId, chunkIndex)`.

### Reconnection

Client reconnects with secure session cookie and `afterSequence`. Server replays retained control events (target: 5 minutes/2,000 events, never raw microphone bytes), then returns live flow. If the cursor expired, server sends `SESSION_RESUME_EXPIRED`; the client restores persisted transcript/history and starts a new realtime session.

### Cancellation and barge-in

Client immediately stops Web Audio nodes and advances a local playback generation, then sends `assistant.interrupted` with `turnId`. Server marks cancellation, aborts STT/LLM/TTS work where supported, discards late vendor frames by generation, emits one authoritative interruption, and never appends late completion as assistant content.

### Backpressure

Audio uses 20–100 ms chunks and a bounded send queue. Above 1 second buffered audio, client pauses capture delivery and shows network state; above 3 seconds it cancels rather than silently recording. Server limits message size, bitrate, session duration, and concurrent turns.

## Alternatives considered

SSE cannot accept microphone frames; raw vendor events couple the client; WebRTC data channels alone complicate cascade/debugging. WebSocket control plus optional WebRTC media is the balanced choice.

## Reasoning

Explicit order, deduplication, replay, and cancellation make provider fallback and mobile reconnect behavior testable.

## Risks

JSON overhead and dual binary/control correlation can cause bugs. Contract fixtures and sequence-property tests are mandatory.

## Acceptance criteria

- Every required event validates against the schema.
- Duplicate/reordered fixtures converge to one transcript and one completed/cancelled turn.
- Local barge-in stop is measured separately from provider cancellation.
- Reconnection never replays microphone payloads.

