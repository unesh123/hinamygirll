# Execution milestone evidence — 2026-10-20

Scope: clause-level request authorization, one real PDF workflow, and read-only ingress diagnosis. No deployment, DNS change, new provider, memory engine, migration, avatar redesign, or multi-agent framework was introduced. Existing RAG/Freepik edits were preserved.

## Changes and relevant diff

| Exact repository-relative path | Milestone change |
|---|---|
| `apps/api/hinaa_api/tools/request_contract.py` | New typed versioned request/clauses with modes and deliverables; protect quoted history before splitting clauses |
| `apps/api/hinaa_api/tools/intent_gate.py` | Replace the previous whole-document leading-word ban with per-clause authorization; retain discussion in the contract, scope negation, preserve illustration and separately requested document formats |
| `apps/api/hinaa_api/artifacts/document_validation.py` | Parse PDFs, validate OOXML ZIP/XML and text, record size/hash/time/path before success |
| `apps/api/hinaa_api/tools/pdf_generate.py` | Catch worker/validation failures; register sidecar only after PDF validation; return artifact ID and hash |
| `apps/api/hinaa_api/tools/document_generate.py` | Validate existing exporters before returning success/registration |
| `apps/api/hinaa_api/main.py` | Revalidate PDF bytes on download; return 422 for corrupt PDFs |
| `apps/web/src/features/actions/intentMatcher.ts` | Retire competing local media/document execution drafts; send the whole request through chat/backend authorization |
| `apps/web/src/features/actions/useActionEngine.ts` | Refuse to commit persisted legacy media drafts as successful actions |
| `apps/web/src/features/actions/components/PdfCard.tsx` | Remove filler-document creation and false ready/download states; old outlines display as drafts |
| `apps/web/src/features/chat/components/VerifiedDocument.tsx` | Pending → download and hash verification → completed; failed checks show an error without a download card |
| `apps/web/src/features/chat/components/GenericResultRenderer.tsx` | Integrate verification gate and unwrap the actual HTTP execution envelope |
| `apps/api/tests/test_execution_milestone.py` | Routing, multi-deliverable gate, real worker/HTTP integration, missing/corrupt output, worker failure and download failure tests |
| `apps/api/tests/test_pdf_generate.py` | Replace invalid fake PDF bytes with valid generated test PDFs; retain source/layout assertions |
| `apps/web/src/features/actions/intentMatcher.test.ts` | Assert media requests remain with backend authorization |
| `apps/web/src/features/chat/components/VerifiedDocument.test.tsx` | Pending/success, missing validation, network failure, 404 and byte mismatch tests |
| `apps/web/src/features/chat/components/GenericResultRenderer.test.tsx` | Verified fixtures and actual tool-envelope regression |
| `scripts/verify_document_milestone.py` | Repeatable real local PDF generation + live HTTP download + SHA-256 evidence |
| `docs/evidence/document-milestone-2026-10-20.json` | Actual PDF/download record |
| `docs/evidence/ingress-vercel-2026-10-20.json` | Read-only Vercel production inspection |

Important behavior: “Explain the layout, then create the PDF” retains a discussion clause and an execution clause. “Do not generate an image; create a PDF report” authorizes the document only. “Create a report with an illustration” retains both tool requests. PDF plus DOCX requests retain both formats. Capability questions, protected historical quotations, cancellation, and the `generate-images` folder example have regression coverage. This is an incremental parser for document/image requests; other tool families still use the existing router.

## Commands and results

Backend:

```powershell
& apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_execution_milestone.py apps/api/tests/test_tool_intent_gate.py apps/api/tests/test_document_discussion_routing.py apps/api/tests/test_pdf_generate.py apps/api/tests/test_document_generate.py apps/api/tests/test_image_search_intent.py apps/api/tests/test_web_search_intent.py apps/api/tests/test_hinaa_intent_gate.py apps/api/tests/test_pdf_generate_quality.py apps/api/tests/test_response_lifecycle.py -o addopts= -q
```

Result: **182 passed**, one existing Google SDK deprecation warning. This is the focused milestone/regression set, not the complete backend suite.

Frontend:

```powershell
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
```

The final full frontend run passed **92 files / 612 tests**, with **2 todo**. TypeScript and build passed; existing large-chunk and ineffective-avatar-dynamic-import warnings remain. A final focused action/component run passed **36 tests**. Existing persisted card data is retained; legacy PDF outlines display as drafts and cannot be newly committed as successful generated files.

```powershell
& apps/api/.venv/Scripts/python.exe scripts/verify_document_milestone.py
node tools/deploy/node_modules/vercel/dist/index.js inspect https://hinaa-workspace.vercel.app --json
```

Both succeeded. An initial ancillary backend command named a nonexistent `test_image_generation_pipeline.py`; it ran no tests and was replaced by the complete valid command above. Initial regression failures exposed lost image-search routing and a duplicate-document issue; both were corrected and the final 182-test run passed.

## One actual artifact

- Request: `Can you create a PDF about my study plan?`
- Source: supplied study-plan text; no model/provider call or fabricated research.
- Worker: actual ReportLab PDF engine.
- Artifact ID: `a5ad640d-849c-45d4-a15f-275880f1091b`.
- File: `apps/api/hinaa_api/data/documents/a5ad640d-849c-45d4-a15f-275880f1091b.pdf`.
- Size: **8,236 bytes**, **3 parsed pages**.
- SHA-256: `5297c44f5992e619c18b6b51bdfd04bb5dbc8bdd559517cd8cadd6cf0da467b9`.
- Registration: adjacent `.metadata.json`, written after format validation, with artifact ID/hash/size/validation timestamp.
- Actual live download: `http://127.0.0.1:8000/api/v1/generated-docs/a5ad640d-849c-45d4-a15f-275880f1091b` → **HTTP 200**, `application/pdf`, exact byte and hash match.

Evidence distinctions: the local PDF generation and HTTP download are real. The integration test also executes the actual `/api/v1/tools/execute` handler with an in-process FastAPI TestClient and a temporary database/filesystem. No external model is needed for supplied-text generation. Frontend completion/failure tests use mocked HTTP responses, real byte hashing, and React/jsdom. A signed-in browser journey on the deployed site was not verified. The already-running local API was not restarted; its live download served the artifact, while the new download-validation branch was exercised in TestClient.

## Ingress diagnosis

Read-only inspection identifies production deployment `dpl_8hkavuLJHJMai4sdDJ1q7fy8HSyh`, alias `hinaa-workspace.vercel.app`, state `READY`. Its actual build configuration uses root `vercel.json`, `pnpm --dir apps/web build`, output `apps/web/dist`, Vite and Node 24.x. This is deployment evidence rather than an assumption from a local config file.

| Layer | Observed result |
|---|---|
| Local backend `/health/live` | 200 JSON |
| Local frontend `/` | 200 HTML |
| Local frontend `/api/v1/capabilities` and `/health/live` | 200 JSON through Vite proxy |
| Cloudflare connector process | None running during diagnosis |
| Configured tunnel `leisure-inter-town-possess.trycloudflare.com/health/live` | Unreachable |
| Production frontend `/` | 200 HTML |
| Production `/health/live` | 502 |
| Production `/api/v1/capabilities` | 502 |

The actual deployed rewrites already contain `/health/:path*` and direct `/api/*`, `/v1/*`, and health routes to that ephemeral Cloudflare hostname. The missing rewrite was not the current outage cause. Intended backend topology is the local Windows FastAPI service exposed through Cloudflare, not a separately provisioned cloud API. The local runner state is historical and is not proof of a running tunnel.

Precise public blocker: there is no reachable backend at the deployed rewrite destination. Restoration requires an approved running connector and reachable origin, or an approved stable backend host, followed by deployment of any changed rewrite destination. This milestone explicitly withholds publishing/deployment/DNS authorization, so none was performed.

## Remaining limitations and rollback

- Production is still offline at the API layer; local changes are not deployed.
- Authenticated deployed UI/browser verification remains blocked by public backend failure.
- Existing generated documents without validation records fail closed in the new completed-card UI until regenerated/validated.
- The scoped parser is not a universal natural-language interpreter. It preserves typed discussion clauses, but does not itself author the explanatory answer.
- Multi-deliverable routing preserves authorized calls; this milestone does not implement embedding a generated illustration into a PDF.
- Full-repository `git diff --check` still reports the pre-existing trailing whitespace in RAG and Freepik. Milestone paths pass the whitespace check.
- Avatar/bundle warnings and the prior voice-speed issues are outside this milestone.

Rollback only the hunks listed in the change table. In `intent_gate.py`, remove the contract wrapper/document-format additions and restore the checkpoint's single-router name and document discussion guard. Remove the new validation imports/calls and PDF helper extraction in the two document workers; remove only the new PDF download-validation branch in `main.py`. Restore the checkpoint versions of the local media matcher/card and renderer snippets, not the entire already-dirty files. Remove the newly added contract/validation/verification modules and their milestone tests/script/evidence if no longer needed. The generated sample may be retained or its exact PDF/sidecar pair removed. Do not use `git reset --hard`, checkout whole dirty files, remove other artifacts, or touch RAG/Freepik changes. No database migration, external publication, DNS or production deployment needs rolling back.
