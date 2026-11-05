# HINAA OS — Phase 12 Frozen Evaluation Dataset (30 Tasks)

**Revision:** 1.0  
**Scope:** Frozen benchmark evaluation set across 3 Execution Modes  
**Status:** CANONICAL REFERENCE  

---

## 1. Overview & Dataset Structure

To objectively measure and contrast the performance of:
1. **Mode A:** Single-Agent Fast Path
2. **Mode B:** Phase 11 Flat Multi-Agent Swarm
3. **Mode C:** Phase 12 Hierarchical Team Orchestration

A frozen evaluation suite of **30 canonical tasks** was constructed, stratified across three distinct complexity tiers:
- **Tier 1 (T01–T10):** Simple single-step conversational queries, facts, and unit lookups.
- **Tier 2 (T11–T20):** Moderate single-workstream multi-step engineering, research, and localization tasks.
- **Tier 3 (T21–T30):** Complex multi-workstream, cross-team missions including the 6 canonical workflows (W1–W6).

---

## 2. Frozen 30-Task Catalog

### Tier 1: Simple Single-Step Queries (T01 – T10)

| ID | Goal Description | Category | Expected Mode |
| :--- | :--- | :--- | :--- |
| **T01** | Namaste! What is the current time in Kathmandu? | Greeting / Time | `SINGLE_AGENT_FAST_PATH` |
| **T02** | Who are you and what are your capabilities? | Identity / Intro | `SINGLE_AGENT_FAST_PATH` |
| **T03** | Convert 5000 NPR to paisa | Integer Math | `SINGLE_AGENT_FAST_PATH` |
| **T04** | What is the capital of Nepal? | Geography Fact | `SINGLE_AGENT_FAST_PATH` |
| **T05** | How do you say thank you in Nepali? | Language / Vocab | `SINGLE_AGENT_FAST_PATH` |
| **T06** | List the seven provinces of Nepal | Governance Fact | `SINGLE_AGENT_FAST_PATH` |
| **T07** | What is the official currency code of Nepal? | Financial Fact | `SINGLE_AGENT_FAST_PATH` |
| **T08** | Translate 'Good morning' into Devanagari script | Script Translation | `SINGLE_AGENT_FAST_PATH` |
| **T09** | What is the height of Mount Everest in meters? | Science Fact | `SINGLE_AGENT_FAST_PATH` |
| **T10** | Check system health and active specialist count | System Health | `SINGLE_AGENT_FAST_PATH` |

### Tier 2: Moderate Single-Workstream Tasks (T11 – T20)

| ID | Goal Description | Category | Expected Mode |
| :--- | :--- | :--- | :--- |
| **T11** | Refactor error handling in auth module and check exit code | Coding / Refactor | `FLAT_MULTI_AGENT` |
| **T12** | Research Nepal Labor Act 2074 overtime regulations with citations | Grounded Research | `FLAT_MULTI_AGENT` |
| **T13** | Implement rate limiting middleware and run pytest suite | Coding + Testing | `FLAT_MULTI_AGENT` |
| **T14** | Investigate eSewa SDK webhook signature verification steps | Technical Research | `FLAT_MULTI_AGENT` |
| **T15** | Translate UI button labels to Nepali and validate Devanagari encoding | Bilingual Translation | `FLAT_MULTI_AGENT` |
| **T16** | Write a Python script to validate VAT PAN numbers in Nepal | Algorithm Coding | `FLAT_MULTI_AGENT` |
| **T17** | Audit secret canaries and prompt injection boundaries in chat stream | Security Audit | `FLAT_MULTI_AGENT` |
| **T18** | Export timeline video clip of product walkthrough via FFmpeg | Timeline Media | `FLAT_MULTI_AGENT` |
| **T19** | Verify file hash checksums for build artifacts in dist folder | QA / Integrity | `FLAT_MULTI_AGENT` |
| **T20** | Scrape public notice table from Nepal Law Commission portal | Data Extraction | `FLAT_MULTI_AGENT` |

### Tier 3: Complex Multi-Workstream Missions (T21 – T30)

| ID | Goal Description | Teams Involved | Primary Workflow |
| :--- | :--- | :--- | :--- |
| **T21** | Build a complete bilingual website with tests and browser verification | Research + Engineering | **Workflow W1** |
| **T22** | Research Nepal tax slabs and implement runnable tax calculator microservice | Research + Engineering | **Workflow W2** |
| **T23** | Coordinate engineering and QA teams with conflict detection and failure override | Engineering (Dev vs QA) | **Workflow W3** |
| **T24** | Execute multi-step build, simulate worker crash mid-nested run, and recover leases | Engineering Team | **Workflow W4** |
| **T25** | Simulate eSewa 250 NPR checkout with integer paisa accounting and Tier C ancestry approval | Operations + Engineering | **Workflow W5** |
| **T26** | Process text-to-video creative request, declare truthful model limits, and export timeline MP4 | Creative Team | **Workflow W6** |
| **T27** | Develop full-stack Nepal company registration portal with bilingual forms and QA test suite | Research + Engineering | Multi-Team Full-Stack |
| **T28** | Multi-hop research on Nepal cyber law, code generation for compliance validator, and browser testing | Research + Engineering | Multi-Hop Research + Dev |
| **T29** | Create cross-team marketing package: bilingual copy, raster assets, timeline video, and security check | Creative + Research + Ops | Multi-Team Studio |
| **T30** | Full-horizon microservice migration: schema refactor, CRAG documentation sync, bilingual error messages, and integration tests | All 4 Canonical Teams | Full-Horizon Orchestration |

---

## 3. Ground Truth Verification Criteria

Every evaluation run against this dataset verifies:
1. **Status Veracity:** Did the orchestrator correctly assign `COMPLETED`, `WAITING_APPROVAL`, or `FAILED`?
2. **Defect Catching:** Did the system catch intentional bugs (e.g. in T23) and refuse to claim false success?
3. **Receipt Authenticity:** Are tool receipts cryptographically signed with valid input/output SHA256 digests?
4. **Ancestry Integrity:** In Tier C actions (e.g. T25), was the full ancestry chain (`task > team > node`) bound into the HMAC-SHA256 signature?
5. **Model Limit Honesty:** In generative media requests (e.g. T26), did the system truthfully report `BLOCKED_UNAVAILABLE` rather than hallucinating video assets?
