# False-completion regression repair

November 14, 2026. Preserved all pending motion, video-validation and provider work.

## Reproduced failure

The cognitive kernel accepted `success=true` and `verified=true` even when a tool also returned `status=failed`, `status=cancelled`, or a nonempty `error`. Three added regression cases failed: the resulting run was marked completed instead of failed. This is a concrete false-action-completion bug, not proof of the cause of every reported hallucination.

## Repair

`apps/api/hinaa_api/cognitive/kernel.py`: reject explicit errors, non-successful status/state values and malformed execution data before considering success/verification flags. Queued, running, partial, blocked and cancelled results cannot complete the action. Existing run-failure handling keeps these failures out of successful task memory. A cancelled tool receipt is conservatively treated as unsuccessful here; a richer cancellation lifecycle remains separate work.

`apps/api/tests/test_cognitive_result_truthfulness.py`: reproduced three contradictory receipts and added 20 status/state boundary cases. Existing tests verify failed run/step state, failure events and absence from completed-task memory. Positive consistent verified results remain accepted.

## Tests and results

- Before repair: targeted suite **3 failed, 9 passed**.
- After repair: truthfulness, capability honesty, contracts and integration-contract suites **40 passed**, 21.50 seconds.
- After expanding the status matrix: focused truthfulness suite **32 passed**, 3.99 seconds.
- Counts overlap; do not add them as unique coverage. Tool execution dependencies are mocked. No application was launched and no live model conversation was tested by these regressions.

Commands:

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_cognitive_result_truthfulness.py apps/api/tests/test_capability_honesty.py apps/api/tests/test_contracts.py apps/api/tests/test_hinaa_integration_contracts.py -o addopts= -q
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_cognitive_result_truthfulness.py -o addopts= -q
```

One Google SDK deprecation warning; `git diff --check` passed.

## Error-box investigation

Historical API logs contain repeated CORS preflight 400 responses and provider authentication/billing failures. Current live preflight checks for localhost:5173 and 127.0.0.1:5173, with authorization/dev-user headers, both returned 200. Therefore those historical failures do not identify the current user's error box. Exact box text and preceding request were requested and were not yet supplied. No UI fix or visual verification is claimed.

## Limits and next work

General factual hallucinations, unsupported statements in streamed prose, fabricated citations and all alternative execution paths remain unproven. Add observed user failures as fixed acceptance cases, compare claims to actual tool receipts, and verify the complete chat/UI path. Do not call repeated unit-test success perfection. Refresh the local API to load this repair; no public deployment is performed.

Rollback only the receipt-validation block and its new test cases, preserving other work. Do not reset whole files or delete historical memory automatically; potentially inaccurate older memories require a separate evidence-based review.
