# 27 — Tier A verification report

## Branch / working tree

- Branch: `phase/3-live-streaming`
- HEAD: `d8653ef` (Phase 2 checkpoint; Phase 3 + Tier A remain uncommitted)
- Paid gate env: absent
- UpCloud gate env: absent
- No commit or push performed during this verification

## Fresh commands (this continuation)

| Command | Result |
|---|---|
| `pytest apps/api/tests -q` (pre Phase 5 additions) | 51 passed |
| `python scripts/validate_blueprint.py` | PASSED |
| `scripts/run_tier_a_provider_gate.py` (no flags) | Exit 2 refuse (correct) |
| `pnpm test` | 22 passed |
| `pnpm typecheck` / `pnpm lint` / `pnpm build` | PASSED |
| `pnpm exec playwright test --workers=2` | 14 passed |

## Verified behaviors

- Prompt layer order and canaries
- Fingerprint stability for identical inputs
- Hinaa ≠ Hiro identity layers with identical safety
- Personality clamp bounds
- Session memory isolation (ephemeral)
- Injection containment in history delimiting
- REST mock plan validation
- Realtime mock WebSocket turn (Playwright)
- Paid provider gate blocked by default

## Differences from docs/26

- This report re-ran commands; it does not invent new Tier A features.
- Subsequent gates in this continuation add Phase 4–7 offline work after this baseline.

## Risks

- Dirty working tree (Phase 3 + Tier A + later gates) is not a reproducible release revision until the owner commits.
- Real provider quality remains unmeasured.
- VRM assets remain quarantined.

## No-commit confirmation

No git commit, push, merge, tag, or history rewrite was performed.
