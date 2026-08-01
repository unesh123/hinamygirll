# HINAA contracts

Protocol `1.0` schemas are compatibility boundaries. Consumers reject unknown major versions; minor additive event types require capability negotiation. Schemas use JSON Schema 2020-12 and `additionalProperties:false` at security-sensitive objects.

- [AssistantTurnPlan](schemas/assistant-turn-plan.schema.json)
- [Realtime event](schemas/realtime-event.schema.json)
- [Phase 2 HTTP stream event](schemas/phase-2-stream-event.schema.json)
- [Phase 3 live WebSocket message](schemas/phase-3-live-message.schema.json)
- [Examples](examples/)

Generated language types may be added in Phase 1; the JSON Schemas remain canonical.

The bounded Phase 2 NDJSON bridge remains the fallback. Phase 3 uses JSON control descriptors followed by bounded binary PCM frames; every emitted `assistant.plan` is validated against canonical `AssistantTurnPlan` before performance fields reach the avatar.
