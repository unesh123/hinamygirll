# HINAA OS — PHASE 05 TEST EVIDENCE AND VERIFICATION AUDIT
## COMPLETE AUTOMATED TEST SUITE RUNS AND PRODUCTION BUILD LOGS

**Document ID:** `PHASE_05_TEST_EVIDENCE`  
**Phase:** 05 — Singularity Evolution  
**Date:** 2026-11-12  
**Baseline Git Commit:** `e76ae7f`  

---

## 1. BACKEND TEST SUITE EXECUTION (PYTEST)

Command executed:
```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_provider_completeness.py apps/api/tests/test_primary_breaker_gate.py apps/api/tests/test_brain_ledger_badge.py apps/api/tests/test_authorization_matrix.py apps/api/tests/test_document_upload_recovery.py
```

### Result: 99 Passed in 55.69s
```text
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.5.0
rootdir: C:\Users\unesh\OneDrive\all my cloud stroge\Desktop\APPS\HINAMYGIRL\apps\api
configfile: pyproject.toml
collected 99 items

apps\api\tests\test_provider_completeness.py ........................... [ 27%]
.....................................                                    [ 64%]
apps\api\tests\test_primary_breaker_gate.py ....                         [ 68%]
apps\api\tests\test_brain_ledger_badge.py ....                           [ 72%]
apps\api\tests\test_authorization_matrix.py .......                      [ 79%]
apps\api\tests\test_document_upload_recovery.py .....................    [100%]

============================== warnings summary ===============================
apps\api\.venv\Lib\site-packages\google\genai\types.py:42
  DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17
======================== 99 passed, 1 warning in 55.69s =======================
```

---

## 2. LARGE PROMPT & UNIVERSAL INGESTION TEST SUITE

Command executed:
```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_large_prompt_ingestion.py
```

### Result: 5 Passed in 1.38s
```text
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.5.0
rootdir: C:\Users\unesh\OneDrive\all my cloud stroge\Desktop\APPS\HINAMYGIRL\apps\api
configfile: pyproject.toml
collected 5 items

apps\api\tests\test_large_prompt_ingestion.py .....                      [100%]

======================== 5 passed, 1 warning in 1.38s =========================
```

**Verified Test Cases:**
1. `test_turn_request_accepts_large_prompts`: Validates that 50,000-char and 150,000-char prompts parse with zero Pydantic validation errors.
2. `test_prompt_input_and_user_block_accommodates_large_prompts`: Validates that `PromptInput` and `build_user_block` accommodate 60,000-char specifications without hardcoded truncation.
3. `test_extract_text_document_does_not_truncate_at_10000`: Validates that 39,000-char source code files are parsed completely without truncation.
4. `test_resolver_code_extensions_and_pdf_dispatch`: Validates that `.tsx` and `.py` code files and `.pdf` documents dispatch correctly through the media resolver.
5. `test_stream_turn_endpoint_accepts_large_prompt_without_422`: Validates that a 30,000-char user turn submitted to `/v1/conversations/turns:stream` succeeds with HTTP 200 without raising `String should have at most 8000 characters`.

---

## 3. FRONTEND TEST SUITE (VITEST)

Command executed:
```powershell
pnpm --filter web test src/design-system/chat/ComposerV6.test.tsx src/design-system/modes/WorkMode.test.tsx
```

### Result: 32 Passed in 27.81s
```text
 ✓ src/design-system/chat/ComposerV6.test.tsx (3 tests) 716ms
 ✓ src/design-system/modes/WorkMode.test.tsx (29 tests) 3747ms

 Test Files  2 passed (2)
      Tests  32 passed (32)
   Duration  27.81s
```

---

## 4. FRONTEND PRODUCTION BUILD

Command executed:
```powershell
pnpm --filter web build
```

### Result: Exit code 0 (0 TypeScript errors)
```text
$ tsc -b && vite build
vite v8.1.5 building client environment for production...
transforming...✓ 6442 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                           3.22 kB │ gzip:   1.18 kB
dist/assets/index-DD4o6ktr.css                          297.82 kB │ gzip:  56.61 kB
dist/assets/index-B8FnybKx.js                           859.43 kB │ gzip: 224.47 kB
dist/assets/vendor-mermaid-CKOaAWe7.js                3,097.60 kB │ gzip: 825.21 kB
✓ built in 4.15s
```

---

## 5. LIVE RUNTIME VERIFICATION EVIDENCE

### A. Health Endpoint Check
```powershell
curl http://127.0.0.1:8000/health/live
```
**Response:** `{"status":"ok","service":"hinaa-api","version":"0.3.0"}` (HTTP 200)

### B. Live Large Turn Stream Check
```python
# Payload: 20,000 characters prompt text sent to /v1/conversations/turns:stream
# Response: HTTP 200 OK, 9 NDJSON events streamed
# Error check: "String should have at most 8000 characters" -> NOT PRESENT
```

### C. Live Gemini 3.5 Flash Inference Check
```python
# Payload: 10,000 characters prompt text sent to /v1/conversations/turns:stream (providerMode: "real")
# Response: HTTP 200 OK, streamed plan returned in 4.5s
```
