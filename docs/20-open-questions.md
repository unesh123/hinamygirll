# Open questions

## Purpose

Record decisions that are genuinely unresolved but do not block this blueprint.

## Decision

| ID | Question | Needed by | Resolution evidence / default meanwhile |
|---|---|---|---|
| OQ-01 | Which exact temporary female/male VRMs may be used and redistributed? | Phase 1 | embedded VRM terms + source screenshot/date; quarantine current files |
| OQ-02 | Which Android phones/browser versions define supported baseline? | W2 | owner devices and WebGL/audio feature test; Chrome current + text fallback |
| OQ-03 | Which auth issuer is available/acceptable? | Phase 5 | ADR after local/demo constraints; local anonymous demo IDs only |
| OQ-04 | Which Azure region has Speech and student quota? | Phase 2 | portal capability test; no architecture dependency on a named region |
| OQ-05 | Does selected Nepali TTS emit word/viseme boundary events in actual SDK path? | Phase 2 | recorded capability spike; assume no viseme and retain fallback |
| OQ-06 | Institutional retention/consent requirements? | before recording | supervisor/ethics approval; collect no participant audio beforehand |
| OQ-07 | Final evaluation thresholds for “acceptable” WER/MOS/FPS? | W2 pre-registration | supervisor-approved baselines; report continuous results regardless |
| OQ-08 | Hosting choice: Container Apps vs App Service/static vendor? | Phase 6 | measured cold start, credit/quota, cost and operational comparison |
| OQ-09 | Is direct realtime speech-to-speech worth MVP scope? | end Phase 2 | language/latency/privacy benchmark; cut by default if cascade meets demo |
| OQ-10 | What name/appearance trademark review is required for public release? | post-MVP | legal/domain search; academic internal use only meanwhile |

## Alternatives considered

Guessing these would create false certainty. Asking now would unnecessarily block documentation because safe defaults exist.

## Reasoning

Each question has a deadline, evidence type and conservative default.

## Risks

Late answers can force rework. Review at every phase gate.

## Acceptance criteria

No question passes its “needed by” gate unresolved; decisions become ADRs or dated records.

