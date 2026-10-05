# Hina provider reliability upgrade

Completed on 2026-10-05, prioritizing AI quality and model providers.

## Result

- Groq and Experiential Labs participate in provider discovery and automatic routing. Configured gateway modes survive settings reloads instead of silently reverting to another provider.
- Experiential uses its configured endpoint, default model, and allowlist. Offline Demo and Local requests remain offline even when a cloud model was previously saved.
- Gemini discovery IDs map consistently to the Gemini request mode in both model pickers. Gemini text requests no longer require unrelated speech credentials.
- Newly integrated OpenAI-compatible adapters participate in vision routing and fallback selection. The existing checks for text-only model names still apply.
- Missing credentials and invalid model choices retain their explanatory streaming errors instead of crashing during recovery.
- Rate-limit failures report degraded health. Experiential health resets when its credential or endpoint changes. Ollama probe results are scoped to the running app and endpoint.
- Provider refresh has a deadline, retry backoff, visibility handling, cancellation, and protection against stale responses. Cached availability is cleared when the backend disconnects.
- Model menus use the backend catalog, preserve provider identity for duplicate model IDs, disable unavailable lanes, and support keyboard navigation and focus restoration.
- Settings has a full-width content area on mobile, scrollable category navigation, labeled controls, and a manual provider refresh action. Cloud voice availability also respects backend connectivity.

## Verification

- Backend: **243 tests passed** across provider configuration, routing, discovery, gateway adapters, probe caching, health reporting, vision, API streaming, response quality and continuity, and stream decoding.
- Frontend: **71 test files passed; 497 tests passed; 2 existing todo cases**. Ran with four workers after an existing markdown test timed out during concurrent build/testing. The final complete run passed without changing that test's timeout or assertions.
- Production: TypeScript compilation and Vite production build passed. The build retains warnings about large bundles.
- Browser: verified mobile provider settings, disabled Local during backend outage, automatic Demo recovery, and manual refresh. Screenshot: [provider settings](screenshots/provider-reliability-2026-10-05.jpg).
- Whitespace checks passed for the touched source paths with the repository's CRLF convention accounted for.

Frontend command, from `apps/web`:

```powershell
node node_modules/vitest/vitest.mjs run --silent --maxWorkers=4
```

Production command, from the repository root:

```powershell
pnpm --dir apps/web build
```

Backend regression files, from `apps/api`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_provider_completeness.py tests/test_api.py tests/test_experiential_gateway.py tests/test_claude_provider.py tests/test_ollama_provider.py tests/test_probe_cache.py tests/test_brain_ledger_badge.py tests/test_vision_routing.py tests/test_config.py tests/test_provider_security.py tests/test_omniroute_fallback.py tests/test_response_quality_and_continuity_fixes.py tests/test_response_quality.py tests/test_display_stream_decoder.py tests/test_qwen_provider.py --tb=short --show-capture=no -q -p no:cacheprovider --basetemp=.pytest_tmp_provider_verification
```

## Limits of verification

Provider tests mock external HTTP responses. No paid live model requests were sent, and provider credentials were not changed. Actual model availability, vision support, streaming behavior, quota, and latency still need verification against each configured upstream endpoint.

The local backend was not running during the browser check, which verified outage behavior. This pass improves provider infrastructure and the related UI; it does not certify every voice, media, avatar, tool, or external integration. Existing frontend todo cases cover microphone permission and external-action confirmation.

Pre-existing workspace changes were preserved. Nothing was deployed or published.
