# Agent Router Runtime Evaluation

To verify that the Agent Router is configured correctly without draining credits or exposing keys, HINAA provides a gated runtime evaluation script.

## Running the Evaluation

The smoke test is located at `scripts/test_agent_router.py`.

It requires explicit confirmation to run, as it makes real network calls:

```powershell
$env:HINAA_ALLOW_AGENT_ROUTER_TEST="1"
$env:HINAA_AGENT_ROUTER_TEST_CONFIRM="I_UNDERSTAND_THIS_MAY_COST_MONEY"
python scripts/test_agent_router.py
```

## What It Tests
1. Reads `AGENT_ROUTER_API_KEY` and `AGENT_ROUTER_BASE_URL` from `.env.local`.
2. Tests the `/v1/models` discovery endpoint (if supported by the provider) to fetch active models.
3. Fires a single, highly constrained request (`max_tokens: 10`) to `/v1/chat/completions`.
4. Validates the streaming response format (Server-Sent Events) and latency.
5. Emits timing logs (First Event, First Text Delta, Completion).
6. Strips the gate variables from the process environment before running to prevent sub-process leakage.
