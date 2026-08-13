# QwenCloud API Contract — 2026-08-13

## Official sources

1. [QwenCloud OpenAI compatibility overview](https://docs.qwencloud.com/api-reference/toolkitframework/openai-compatible/overview)
2. [QwenCloud first API call](https://docs.qwencloud.com/developer-guides/getting-started/first-api-call)
3. [QwenCloud API key documentation](https://docs.qwencloud.com/api-reference/preparation/api-key)
4. [Qwen API Platform](https://qwen.ai/apiplatform)

## Integration facts used by HINAA

QwenCloud documents an **OpenAI-compatible Chat Completions API**. The SDK base URL for the standard international compatible interface is:

```text
https://dashscope-intl.aliyuncs.com/compatible-mode/v1
```

HINAA must use Bearer authentication and preserve the key only in the backend environment. QwenCloud documentation advises users to configure an environment variable instead of hard-coding the key; its dashboard key is generated at `https://home.qwencloud.com/api-keys` and may use `sk-ws-` formatting.

For Chat Completions, QwenCloud states that `response_format` supports `json_object`, which matches HINAA’s structured AssistantTurnPlan protocol. It documents `max_tokens`; it lists `max_completion_tokens` among unsupported parameters that are silently ignored. Therefore HINAA’s Qwen path sends `max_tokens` and does not rely on raw streaming JSON for presentation. The provider buffers and validates the plan before emitting natural `displayText` in live mode.

Documented current model examples include `qwen3.7-plus` and `qwen3.8-max`; the API platform lists Qwen3.7 Plus, Qwen3.7 Max, Qwen3.6 Plus, Qwen3.5 Flash, and multimodal/ASR/TTS variants. HINAA’s default text-brain selection is `qwen3.7-plus`, with the model list constrained by user-controlled backend environment configuration.

QwenCloud also advertises a Realtime API, but this HINAA pass intentionally uses the existing local microphone/STT → Qwen text brain → ElevenLabs TTS pipeline. Native Qwen realtime transport has not been implemented or claimed.

## Security boundary

No actual Qwen credential is contained in this file, repository changes, logs, or documentation. The implementation accepts `HINAA_QWEN_API_KEY` first, with `QWEN_API_KEY` and `DASHSCOPE_API_KEY` as backend-only compatibility aliases.
