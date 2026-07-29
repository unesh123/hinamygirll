# HINAA contracts

Protocol `1.0` schemas are compatibility boundaries. Consumers reject unknown major versions; minor additive event types require capability negotiation. Schemas use JSON Schema 2020-12 and `additionalProperties:false` at security-sensitive objects.

- [AssistantTurnPlan](schemas/assistant-turn-plan.schema.json)
- [Realtime event](schemas/realtime-event.schema.json)
- [Examples](examples/)

Generated language types may be added in Phase 1; the JSON Schemas remain canonical.

