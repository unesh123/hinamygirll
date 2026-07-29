# HINAA contracts

Protocol `1.0` schemas are compatibility boundaries. Consumers reject unknown major versions; minor additive event types require capability negotiation. Schemas use JSON Schema 2020-12 and `additionalProperties:false` at security-sensitive objects.

- [AssistantTurnPlan](schemas/assistant-turn-plan.schema.json)
- [Realtime event](schemas/realtime-event.schema.json)
- [Phase 2 HTTP stream event](schemas/phase-2-stream-event.schema.json)
- [Examples](examples/)

Generated language types may be added in Phase 1; the JSON Schemas remain canonical.

The bounded Phase 2 NDJSON bridge does not replace the Phase 3 WebSocket envelope. Every emitted `plan` still references and validates against canonical `AssistantTurnPlan`.
