# Status and bounded repair — November 14, 2026

Baseline: `ef2786d`; working tree clean on entry. Recent commits add Coarena UI/backend selection, fal.ai and Hugging Face video adapters, and merged improvements to computer-action truthfulness, cancellation receipts and multi-repository GitHub handling. Previous execution repairs remain present. Code presence is not live acceptance.

## Repaired

- `apps/api/hinaa_api/services.py`: Coarena rejects an unsupported explicitly selected model with `PROVIDER_MODEL_NOT_ALLOWED` (422), instead of silently running its default model.
- `apps/api/hinaa_api/brain_ledger.py`: Coarena health evidence now fingerprints its credentials, endpoint and default model. Changing these invalidates old evidence.
- `apps/api/tests/test_coarena_provider.py`: added rejected-model and credential/endpoint/model fingerprint regressions.
- `scripts/check_configured_chat.py`: added Coarena to the explicit bounded live diagnostic.

No credentials, default models, public deployment, branches or other provider integrations were modified.

## Actual checks

Local frontend and API health returned HTTP 200 before the API refresh.

Live synthetic Coarena check used its configured default `claude-sonnet-5-5`, with no fallback. Result: connection failure in 109 ms before an HTTP response. DNS resolved. A separate unauthenticated reachability request also failed with ConnectionResetError in the exception chain. This does not establish an invalid API key, a billing failure or the location of the reset. The provider's model name is a gateway label, not independently verified model identity. Evidence: `.runtime/coarena-check-2026-11-14.json`.

Command:

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_coarena_provider.py apps/api/tests/test_provider_completeness.py apps/api/tests/test_configured_chat_check.py apps/api/tests/test_capability_honesty.py apps/api/tests/test_hina_phase4_free_video.py -o addopts= -q
```

Result: **73 passed**, 21.03 seconds; one Google SDK deprecation warning. Provider/video unit tests use mocks; no live video was generated and no free-credit or output-quality claim was verified. `git diff --check` passed with line-ending notices only. No frontend code changed in this milestone.

## Next completion gates

1. Diagnose gateway transport/reset and prove usable model output before describing Coarena as available. Other providers' historical successes must be refreshed before relying on them.
2. Prove one video request through the real app to a decoded, downloadable artifact. Verify actual account quota, model availability, cancellation and error handling; do not equate an API key or MP4-looking bytes with success.
3. Complete actual request-to-PR orchestration, desktop tasks and process-crash recovery from the master handoff. Existing PRs, tool registration and local fixtures alone do not prove them.
4. Measure microphone-to-playback latency and avatar frame times on real hardware. Current testing does not certify either.
5. Verify authenticated public ingress and endurance before release. No deployment was performed here.

The master phase plan remains `docs/ANTIGRAVITY-MASTER-HANDOFF-2026-11-13.md`; update its evidence as gates pass rather than restarting the architecture.

Rollback: reverse only this milestone's four source/test/script changes, preserving subsequent work. Do not reset entire files. Refresh the owned API after reversal. The synthetic ledger observation expires normally; do not delete unrelated runtime evidence.
