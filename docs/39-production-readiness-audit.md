# 39 — Production-readiness audit

Legend: Verified | Partially verified | Blocked | Not implemented | Not applicable

| Category | Item | Status | Evidence |
|---|---|---|---|
| Functional | Mock conversation | Verified | pytest, Vitest, Playwright |
| Functional | Realtime mock WS | Verified | test_realtime, Playwright |
| Conversation | Tier A prompt brain | Verified offline | prompt tests |
| Language | Real Gemini/Azure quality | Blocked | Gate 1 not authorized |
| Voice | Real Azure STT/TTS | Blocked | Gate 1 not authorized |
| Realtime | Interruption mock | Verified | realtime tests |
| Avatar | Performance scheduler | Partially verified | unit tests; amplitude lips only |
| Avatar | Licensed VRM | Blocked | ASSET_LICENSES quarantined |
| Memory | Explicit CRUD | Partially verified | SQLite/dev auth tests |
| Memory | Postgres RLS / OIDC | Not implemented | ADR-012/013 |
| Privacy | Dashboard API | Partially verified | `/v1/privacy/*` |
| Privacy | Polished UI | Partially verified | minimal panel if present |
| Security | Secret-free client | Verified | architecture + reviews |
| Security | Prod auth | Blocked | OIDC incomplete |
| Reliability | Paid latency | Blocked | not measured |
| Accessibility | Reduced motion / text-only | Verified | Playwright |
| Cost | Inventory | Verified empty | no cloud resources |
| Deployment | HTTPS staging | Blocked | UpCloud not authorized |
| Backup | Restore drill | Not implemented | — |
| Licence | VRM ship | Blocked | quarantined |
| Demo | Mock contingency | Verified | mock mode |

## Release blockers still open

- Real provider untested for any real-provider release claim  
- No HTTPS staging / Android trusted mic proof  
- No OIDC production auth  
- No backup restore  
- VRM licence unknowns  
- Dirty uncommitted tree (reproducibility)

## Recommendation

**Ready for local demo only** (mock/text).  
Not ready for limited private beta or public production.
