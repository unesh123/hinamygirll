# Error handling

## Purpose

Give each failure a stable code, user action, fallback, and telemetry policy.

## Decision

Errors use `{code,message,retryable,userActionRequired,correlationId,details?}`; `details` is safe and never includes prompts, audio, keys or vendor bodies.

| Code / condition | User message | Retry / fallback | Level; telemetry | Action? |
|---|---|---|---|---|
| MIC_PERMISSION_DENIED | “Microphone is off. You can type instead.” | after settings; text | info; browser,permission | yes |
| CAMERA_PERMISSION_DENIED | “Camera wasn’t enabled.” | optional; mock/no camera | info; browser | optional |
| AUDIO_NO_SIGNAL | “I couldn’t hear anything. Try again?” | yes; text | info; RMS,duration | yes |
| STT_LANGUAGE_MISMATCH | “That transcript may be wrong—please edit it.” | yes; editable text | warn; selected/detected locale | yes |
| PROVIDER_TIMEOUT | “The service is taking too long.” | bounded retry/fallback | warn; provider,stage,latency | no |
| PROVIDER_RATE_LIMIT | “That service is busy. I can try another.” | Retry-After/fallback | warn; provider,retry_after | maybe |
| PROVIDER_KEY_INVALID | “This provider needs its connection fixed.” | no; mock/other | error; connection ID only | yes |
| NETWORK_OFFLINE | “You’re offline. Mock and saved chat are available.” | auto reconnect; mock/text | info; network type | no |
| REALTIME_DISCONNECTED | “Voice disconnected; reconnecting…” | resume cursor; cascade/text | warn; seq,attempt | no |
| TTS_FAILED | “I can show the answer, but voice failed.” | one retry; text | warn; provider,voice | no |
| AUDIO_PLAYBACK_FAILED | “Audio couldn’t play. Tap to retry.” | user gesture; text | warn; codec,autoplay state | yes |
| MODEL_RESPONSE_INVALID | “I had trouble forming that answer.” | one repair; neutral plan | error; schema path/model config | no |
| EMOTION_SCHEMA_INVALID | no separate alarm | neutral expression | warn; field/value category | no |
| VRM_LOAD_FAILED | “Avatar unavailable; chat still works.” | retry; portrait/text | error; asset hash,stage | no |
| ANIMATION_LOAD_FAILED | “Using simple motion.” | base idle | warn; cue key/hash | no |
| WEBGL_UNAVAILABLE | “3D isn’t supported here; using text mode.” | portrait/text | info; renderer info | no |
| DATABASE_UNAVAILABLE | “History can’t be saved right now.” | read-only/private ephemeral | error; operation,latency | maybe |
| MEMORY_RETRIEVAL_FAILED | no disruption | answer without memory | warn; user hash,count | no |
| TOOL_EXECUTION_FAILED | “The action did not complete.” | future: safe/idempotent retry | error; tool/action ID | maybe |
| DEVICE_RESOURCE_LOW | “Switching to low-quality mode.” | degrade/static | info; frame/memory/battery API flag | no |
| BROWSER_UNSUPPORTED | “Use supported Chrome/Edge or text mode.” | text-only | info; UA family/features | yes |
| SESSION_RESUME_EXPIRED | “Voice session expired; starting a new one.” | new session/history restore | info; last seq | no |

Global exception handlers map internal/vendor errors, redact, attach trace ID, and preserve causal category. Retries are never infinite. UI state machines consume typed categories rather than parsing messages.

## Alternatives considered

Displaying vendor errors leaks details and confuses users. Generic “something went wrong” prevents recovery and research.

## Reasoning

Stable codes decouple localized UX from vendors and support failure-rate metrics.

## Risks

Fallback loops and hidden data loss. Record fallback hops, cap at two, and clearly mark unsaved history.

## Acceptance criteria

Every listed condition has a deterministic test fixture; errors contain no secret/raw content; no retry loop exceeds policy.

