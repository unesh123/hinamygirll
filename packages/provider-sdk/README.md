# Provider SDK interface specification

Provider IDs/model IDs are opaque configuration. Every adapter exposes `describeCapabilities()`, `health()`, `estimateCost(request)`, `close()` and typed operation methods; accepts deadline, cancellation signal, trace context and privacy classification; returns normalized events/usage; and redacts vendor errors.

```text
LLMProvider.streamTurn(messages, responseSchema, options) -> AsyncIterable<TextDelta|StructuredResult|Usage>
RealtimeVoiceProvider.createEphemeralSession(options) -> EphemeralSessionDescriptor
STTProvider.transcribeStream(audio, options) -> AsyncIterable<PartialTranscript|FinalTranscript|Usage>
TTSProvider.synthesizeStream(text, voice, options) -> AsyncIterable<AudioChunk|WordBoundary|Viseme|Usage>
VisionProvider.analyzeFrame(frameRef, purpose, options) -> VisionObservation
ImageGenerationProvider.createJob(spec, options) -> ImageJob       [post-MVP]
EmbeddingProvider.embed(texts, options) -> EmbeddingBatch
ToolProvider.propose/execute(validatedRequest, approval) -> ToolResult [post-MVP; execute disabled]
```

Capabilities include languages, streaming, direct realtime, codecs, word/viseme timing, structured output, data-region/privacy tier, max sizes and ephemeral tokens. Adapter constructors receive resolved secrets through server dependency injection; contracts never accept raw credentials.

Contract tests cover cancellation, deadlines, partial ordering, malformed vendor output, usage reporting, rate limit, auth failure, health, capability mismatch and redaction. Mock adapters are normative fixtures. An adapter cannot choose fallback or write database state; the router/application owns those decisions.

