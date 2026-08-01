# 41 — Pre-provider local checkpoint

## Branch / previous HEAD

- Branch: `phase/3-live-streaming`
- Previous HEAD: `d8653ef` (`checkpoint: complete HINAA phase 2`)
- Checkpoint purpose: freeze offline Phase 3 + Tier A + Phase 4 presence + Phase 5 memory/privacy scaffold + Phase 6–7 planning before any paid provider run or UpCloud provisioning

## Validation (exact results)

| Command | Result |
|---|---|
| `python scripts/validate_blueprint.py` | PASSED |
| `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests -q` | **56 passed** |
| `pnpm typecheck` | PASSED |
| `pnpm lint` | PASSED |
| `pnpm test` | **28 passed** |
| `pnpm build` | PASSED (PWA precache 8 entries) |
| `pnpm exec playwright test --workers=2` | **14 passed** |
| Secret scan (source text) | Clean — only empty test placeholders for `AZURE_SPEECH_KEY=""` / `GEMINI_API_KEY=""` |
| Client bundle secret scan | Clean — no `.env.local` values in `apps/web/dist` |
| `git check-ignore apps/api/.env.local` | Ignored |
| Paid gate without env | Refuses (exit 2) |
| UpCloud gate without env | Refuses (exit 2) |

## Files included (summary)

- Phase 3 realtime API/web stack
- Tier A prompt assembly (`apps/api/hinaa_api/prompts/`)
- Phase 4 performance scheduler (procedural)
- Phase 5 persistence/privacy API + privacy panel
- Offline evaluation corpus/runner
- Docs 25–41, ADRs 012–013, master blueprint
- Infra planning (`infra/upcloud/`, Dockerfile example)
- Gate scripts (paid provider + UpCloud refusal helpers)
- Contracts/OpenAPI/env example updates
- Hardened root `.gitignore`

## Files excluded

- `apps/api/.env.local` and all secrets
- Quarantined/local assets: `*.vrm`, `*.zip`, `52blendshapes-for-VRoid-face-main/`, `AnimationClipToVrmaSample-main/`
- `.venv/`, `node_modules/`, `dist/`, Playwright reports/results
- `*.tfstate*`, SQLite runtime DBs, logs, keys, audio captures
- Terraform applied state (none exists)

## Secret scan result

No high-confidence live credentials found in commit candidates. Required secret **names** present in ignored `.env.local`: `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `GEMINI_API_KEY` (values not displayed or committed).

## Known limitations at checkpoint

- Real Gemini/Azure quality not yet measured (paid gate env not set at checkpoint time)
- VRM still quarantined; amplitude lip sync only
- Dev auth only (`X-HINAA-Dev-User`); OIDC/RLS incomplete
- No UpCloud resources provisioned
- Not production-ready / not private-beta ready

## Authorization notes

- Local commit authorized by owner for this checkpoint only
- Push, merge, rebase, tag, paid calls, and UpCloud provisioning are **not** authorized by this checkpoint document alone
