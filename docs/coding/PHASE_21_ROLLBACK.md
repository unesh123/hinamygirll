# HINAA OS — Phase 21 Rollback & Recovery Specification

## 1. Overview
This runbook defines the verified, deterministic rollback protocol from `phase-21-autonomous-engineering` to `phase-20-checkpoint`.

---

## 2. Checkpoint Hashes & Verification

- **Baseline Annotated Tag:** `phase-20-checkpoint` (`c70928a6506259be34b0169baeb809e22566f36d`)
- **Baseline Commit Hash:** `67d880a16f4eab74c0add02d51b64bf6ca0ca68c`
- **Reversible Feature Branch:** `phase-21-autonomous-engineering`

To verify the tag points to the exact commit before rollback:
```bash
git rev-parse "phase-20-checkpoint^{commit}"
# Output must be: 67d880a16f4eab74c0add02d51b64bf6ca0ca68c
```

---

## 3. Emergency Single-Command Rollback Procedure

If any regression occurs in production, execute:

```powershell
# 1. Stash or discard working tree modifications
git status
git checkout main

# 2. Reset branch to phase-20-checkpoint
git reset --hard phase-20-checkpoint

# 3. Clean temporary runtime workspaces
Remove-Item -Recurse -Force .runtime/coding/workspaces/* -ErrorAction SilentlyContinue

# 4. Verify baseline test suite passes
$env:PYTHONPATH="apps/api"
apps\api\.venv\Scripts\pytest.exe apps/api/tests/coding/test_p20_acceptance_64.py
```

---

## 4. Verification After Rollback

1. Run the 64-scenario Phase 20 acceptance suite:
   ```powershell
   apps\api\.venv\Scripts\pytest.exe apps/api/tests/coding/test_p20_acceptance_64.py
   # Expected: 64 passed in ~3.5s
   ```
2. Verify Phase 19 suite:
   ```powershell
   apps\api\.venv\Scripts\pytest.exe apps/api/tests/coding/test_p19_acceptance_128.py
   # Expected: 128 passed in ~4.2s
   ```
3. Verify PDP Security suite:
   ```powershell
   apps\api\.venv\Scripts\pytest.exe apps/api/tests/security/test_s15_suite.py
   # Expected: 80 passed in ~24s
   ```
4. Verify Multilingual Voice suite:
   ```powershell
   apps\api\.venv\Scripts\pytest.exe apps/api/tests/test_voice_multilingual.py
   # Expected: 5 passed in ~0.2s
   ```
