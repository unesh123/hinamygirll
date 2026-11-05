# HINAA OS — Phase 10 Memory Provenance Schema Specification

## 1. Schema Definition

Every durable memory item stored in HINAA OS contains cryptographic and environmental provenance metadata:

```json
{
  "id": "urn:uuid:6a43f829-19c2-4cf4-b8e7-769a23992019",
  "tenant_id": "default",
  "user_id": "usr_9981",
  "project_id": "prj_nepal_ai",
  "scope": "user",
  "memory_type": "preference",
  "content": "User prefers dark mode UI and FastAPI for backend development",
  "structured_data": {
    "entity": "FastAPI",
    "theme": "dark_mode"
  },
  "trust_tier": "verified",
  "confidence": 0.98,
  "source_url": "https://fastapi.tiangolo.com",
  "source_tool": "browser_research",
  "source_turn_id": "turn_129412",
  "evidence_text": "I always choose FastAPI for async APIs",
  "is_active": true,
  "is_contradicted": false,
  "superseded_by_id": null,
  "created_at": "2026-11-05T06:14:18.297000+00:00",
  "updated_at": "2026-11-05T06:14:18.297000+00:00",
  "expires_at": null,
  "embedding": [0.0381, -0.0192, 0.0821, "..."]
}
```

---

## 2. Field Specifications

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID string` | Globally unique identifier for the memory record. |
| `tenant_id` | `string` | Multi-tenant boundary partition key. |
| `scope` | `enum` | Operational scope: `user`, `project`, `system`, or `session`. |
| `memory_type` | `enum` | Category: `fact`, `preference`, `entity`, `instruction`, `procedure`, `episode`. |
| `trust_tier` | `enum` | Authority tier: `verified`, `user_explicit`, `inferred`, `unverified`, `staged`. |
| `confidence` | `float (0.0–1.0)` | Calibration confidence score. |
| `source_url` | `string \| null` | URL where fact was observed (if discovered by research agent). |
| `source_tool` | `string \| null` | Name of tool generating the assertion (`browser_fetch`, `code_ast`, etc.). |
| `evidence_text`| `string \| null` | Raw snippet or quote supporting the assertion. |
| `is_contradicted` | `boolean` | Flag indicating whether this record has been superseded by a newer claim. |
| `superseded_by_id` | `string \| null` | Pointer to the newer `id` that replaced this assertion. |
| `expires_at` | `ISO datetime \| null` | TTL expiration timestamp. Null indicates permanent retention. |
