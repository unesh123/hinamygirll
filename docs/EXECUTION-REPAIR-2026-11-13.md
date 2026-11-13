# Execution repair — November 13, 2026

This milestone repairs the concrete failures from the current-status review. It does not certify full autonomy or production readiness. Existing and concurrent Phase 07 report edits were preserved. No remote branch, commit, PR, deployment, DNS, credential or public-ingress changes were made.

## Changes

- `apps/api/hinaa_api/repository/github_flow.py`: task commits use literal pathspecs and `git commit --only`, keeping unrelated staged changes out of the commit. The PR method is now asynchronous, requires explicit repository/base, checks the remote branch SHA, creates a draft through the existing GitHub client, and verifies it with a subsequent GET. `mock_remote=True` is rejected instead of generating a fake URL. Callers must await the method; repository search found only test callers of this helper.
- `apps/api/hinaa_api/repository/workspace.py`: NUL-delimited UTF-8 Git status, explicit untracked files and no rename folding keep filenames and scope checking accurate.
- `apps/api/hinaa_api/tools/github_tools.py`: the registered PR tool now creates drafts and verifies the returned remote PR before reporting success. Invalid responses and permission failures remain failures. The governed helper additionally checks expected commit SHA; it does not automatically push a branch.
- `apps/api/tests/test_governed_github_flow.py`: regressions prove unrelated staged and unstaged content is preserved, and remote SHA mismatch/missing results cannot become successful PRs.
- `apps/api/tests/test_github_pr_verification.py`: seven registered-tool tests cover draft creation/readback, wrong URL/branch/state/draft, missing number and permission rejection.
- `apps/web/src/design-system/modes/WorkMode.tsx`, `AdobeMotionTimeline.tsx`, `ShowroomMode.tsx`: remove fabricated 142/180 ms latency and 5.5x improvement defaults. Missing latency is labelled unmeasured. This is truthful telemetry, not a claimed latency improvement.

## Validation actually performed

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_governed_github_flow.py apps/api/tests/test_git_worktrees.py -o addopts= -q
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_github_pr_verification.py -o addopts= -q
```

12 + 7 tests passed. Commit isolation uses real Git in temporary repositories. GitHub network responses are mocked, including the success path; no live PR completion is claimed.

From `apps/web`:

```powershell
node node_modules/typescript/bin/tsc -b
node node_modules/vitest/vitest.mjs run src/design-system/modes/WorkMode.test.tsx src/design-system/modes/WorkMode.regenerate.test.tsx src/design-system/modes/ShowroomMode.test.tsx --maxWorkers=2
node node_modules/vite/bin/vite.js build
```

TypeScript passed; 41 tests passed; production build passed in 2.50 seconds. The large-bundle warning remains. UI tests are jsdom tests, not browser visual or real audio checks. `git diff --check` passed after whitespace cleanup.

## Desktop runtime

Started the existing local supervisor. The paired desktop bridge returned HTTP 200 with `ready`; unpaired health access returned 401. A live read-only `list_windows` action returned success and 35 windows. Window contents/titles and the pairing token were not printed. This proves authenticated bridge communication and enumeration, not arbitrary application-task success. No mouse, keyboard, close-window or shell action was used in this check.

## Remaining acceptance gates

1. Real approved task branch → scoped commit → push → verified draft PR. The remote write permission and full orchestration remain to be proved; failures after a POST require inspecting remote state before retrying.
2. Authorized desktop task with observed output, cancellation and failure recovery.
3. Actual worker-process interruption/restart with no repeated external effects, then a sustained endurance run.
4. Measured microphone-to-transcript/first-token/first-audio/playback timing, interruption, pauses and multilingual acceptance.
5. Real browser/mobile and avatar performance profiling, production ingress checks, and reference-quality creative renders.

GitHub protocol reference: https://docs.github.com/en/rest/pulls/pulls#create-a-pull-request

## Rollback

Reverse only this milestone's hunks in the listed files, preserving later work and the unrelated Phase 07 report modifications. Remove the new PR verification test/report only if they have no subsequent edits. Do not reset entire files or the repository. Rebuild frontend assets and refresh the owned local API after reversing changes. The local supervisor and bridge can be managed using the existing runner controls.
