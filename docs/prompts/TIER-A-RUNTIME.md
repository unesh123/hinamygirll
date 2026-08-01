# Tier A runtime prompt assembly

Executable implementation lives in `apps/api/hinaa_api/prompts/`. The Markdown specs in this folder remain design intent; the Python package is the runtime source of truth for assembled instructions.

## Layer order

1. safety  
2. product_identity  
3. companion_identity  
4. language  
5. personality  
6. response_depth  
7. tool_policy  
8. schema_contract  
9. approved_memory (application-trusted; empty in Tier A)  
10. conversation_history (untrusted)  
11. user_message (untrusted)

## Trusted vs untrusted

- Trusted layers become `system_instruction`.
- History and user text are delimited with `trusted="false"` and placed in provider `contents`.
- Injection text inside history cannot reorder or replace safety layers.

## REST vs realtime

| Mode | Model output | Performance cues |
|---|---|---|
| REST | Structured `AssistantTurnPlan` JSON | Model-proposed, schema-validated; repair once; else fallback |
| Realtime | Streamed natural language text | Server `plan_performance` allowlisted planner after text |

Companion identity, safety, multilingual policy, and personality bounds are shared.

## Versions

- Prompt: `tier-a-conversation-brain-1.0.0`
- Safety: `safety-1.0.0`
- Companions: `companions-1.0.0`

Bump versions when layer wording or bounds change. Fingerprints are SHA-256 over normalized layer payloads.

## Testing

```powershell
apps\api\.venv\Scripts\python.exe -m pytest apps\api\tests\test_prompt_assembly.py apps\api\tests\test_conversation_brain.py -q
```

Paid provider gate: `scripts/run_tier_a_provider_gate.py` (explicit env confirmation required).
