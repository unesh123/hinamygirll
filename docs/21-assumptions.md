# Assumptions

## Purpose

Make non-blocking premises explicit and testable.

## Decision

| ID | Assumption | Validation / failure response |
|---|---|---|
| A-01 | One student delivers over 16 weeks with supervisor access. | confirm W1; reduce scope, not quality gates |
| A-02 | Primary demo is Android Chrome on stable Wi-Fi. | device survey W1; maintain text/offline mock |
| A-03 | Owner can create official Azure/Gemini developer resources but keys are not available during blueprint. | portal check Phase 2; mock remains default |
| A-04 | PostgreSQL can run locally via Docker. | environment spike; SQLite only for mock tests |
| A-05 | Two native Nepali reviewers and consenting adult speakers/raters can be recruited with approval. | confirm before data collection; report smaller approved sample limitation |
| A-06 | Existing binary assets are references, not approved product assets. | licence inventory; quarantine/replace |
| A-07 | MVP scale is <=50 evaluation users and <=20 concurrent sessions. | load test; revisit architecture if pilot exceeds |
| A-08 | No payment, autonomous tools, background capture or public BYOK is needed for grading. | scope approval; treat requests as post-MVP |
| A-09 | English documentation is acceptable, with Nepali UX/evaluation content. | supervisor confirmation; translate key participant materials |
| A-10 | Current official catalogs can change between blueprint and build. | capability checks and dated rate sheets; configuration over constants |

## Alternatives considered

Blocking on every unknown would halt useful work; hiding assumptions would make estimates misleading.

## Reasoning

Each assumption has a validation or conservative response.

## Risks

Owner/supervisor constraints may differ. Update this file and impacted ADR/roadmap when discovered.

## Acceptance criteria

Assumptions are reviewed W1 and each phase gate; invalidated assumptions create a documented change decision.

