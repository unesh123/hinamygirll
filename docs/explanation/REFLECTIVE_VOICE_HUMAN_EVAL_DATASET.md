# HINAA OS — Reflective Voice 30-Artifact Holdout Evaluation Dataset
**Version:** 1.0.0  
**Dataset Reference:** `DATASET-RV-30-HOLDOUT`  
**Evaluation Scope:** Blinded comparative evaluation of standard Read-Aloud recitation vs. Reflective Voice Metacognitive Explanations across English, Devanagari Nepali, and Romanized Nepali.

---

## 1. Dataset Overview

The dataset comprises 30 curated holdout artifacts representing typical long-form outputs generated across HINAA OS phases 01–13. Each artifact has been evaluated across two conditions:
- **Condition A (Baseline):** Verbatim TTS recitation (legacy read-aloud reading raw markdown, markdown tables, bracketed citations, and raw code).
- **Condition B (Reflective Voice):** Metacognitive Explanation Engine using autonomous intent routing, claim extraction, 3-gram novelty verification, and acoustic chunk coordination.

---

## 2. Artifact Taxonomy & Corpus Index

| ID | Title / Topic | Category | Word Count | Language | Primary Challenge Tested |
|---|---|---|---|---|---|
| `ART-01` | Autonomous Swarm DAG Latency Benchmarks | Systems Research | 412 | English | Markdown table stripping, numeric synthesis |
| `ART-02` | SQLite WAL Concurrency & Locking Profile | Systems Research | 358 | English | Technical architecture explanation |
| `ART-03` | Nepal QR Interoperability Specification (NCHL/Fonepay) | Fintech Spec | 480 | English/Nepali | Cross-currency regulatory compliance |
| `ART-04` | FastPath Single-Agent vs Hierarchical Team Latency | Benchmark Report | 520 | English | Comparative cost/latency trade-off analysis |
| `ART-05` | CRAG Zero-Hallucination Retrieval Protocol | AI Research | 390 | English | Evidence grounding & citation filtering |
| `ART-06` | ComfyUI Checkpoint Availability Incident Postmortem | DevOps Incident | 440 | English | Honest disclosure of system limitation |
| `ART-07` | Browser Automation CDP Session Recovery Runbook | Runbook | 360 | English | Step-by-step procedural instruction |
| `ART-08` | Hybrid Lexical-Vector Memory Scoring Formula | Technical Spec | 310 | English | Formula translation to spoken prose |
| `ART-09` | ElevenLabs TTS Streaming WebSocket Protocol | Audio Architecture | 335 | English | Protocol walkthrough without code recitation |
| `ART-10` | Tier C Human-in-the-Loop Approval Policy | Governance Doc | 425 | English | Security policy & permission boundaries |
| `ART-11` | काठमाडौँ उपत्यकाको सार्वजनिक यातायात अनुगमन प्रतिवेदन | Public Policy | 380 | Devanagari Nepali | Devanagari natural phrasing & cadence |
| `ART-12` | नेपाल राष्ट्र बैंक डिजिटल भुक्तानी मार्गदर्शन | Regulatory Doc | 415 | Devanagari Nepali | Formal Nepali administrative vocabulary |
| `ART-13` | साइबर सुरक्षा चेतावनी: फिसिङ आक्रमण नियन्त्रण | Security Alert | 290 | Devanagari Nepali | Urgent alert explanation with clear steps |
| `ART-14` | जलविद्युत आयोजना उत्पादन क्षमता विश्लेषण | Engineering Report | 460 | Devanagari Nepali | Numerical extraction & units handling |
| `ART-15` | मौसम पूर्वानुमान तथा विपद् जोखिम मूल्यांकन | Environmental Data | 340 | Devanagari Nepali | Risk analysis without raw data tables |
| `ART-16` | Hamro Swarm Architecture bujhaideu | System Architecture | 315 | Romanized Nepali | Romanized token parsing & mixed synthesis |
| `ART-17` | Backend ma memory leak kasari fix garne | Debugging Guide | 350 | Romanized Nepali | Technical concepts in Romanized Nepali |
| `ART-18` | Task scheduler crash bhayepachhi k garne | Ops Runbook | 280 | Romanized Nepali | Incident recovery steps in natural dialect |
| `ART-19` | Payment gateway integration verification steps | Fintech QA | 390 | Romanized Nepali | Step-by-step workflow in conversational style |
| `ART-20` | Database indexing best practices ra query plan | Database Guide | 430 | Romanized Nepali | Technical optimization in Romanized mixed |
| `ART-21` | Code Diff: Rust Memory Safety Fix in DAG Engine | Code Diff | 280 | English | Reporting diff semantics without diff syntax |
| `ART-22` | Test Suite Output: 80 Passed, 2 Failed Test Receipts | Test Receipt | 210 | English | Truthful reporting of failing test count |
| `ART-23` | Security Patch: SQL Injection Prevention in FastPath | Code Security | 260 | English | Describing patch logic without raw symbols |
| `ART-24` | Contradictory Source Analysis: FastPath vs Swarm Cost | Contradictory Sources | 540 | English | Balanced synthesis of conflicting viewpoints |
| `ART-25` | Renewable Energy vs Grid Stability Trade-offs | Trade-off Analysis | 490 | English | Alternative perspective & critique framing |
| `ART-26` | Edge Telemetry Pipeline Kafka vs SSE Architecture | Architecture Review | 470 | English | Architectural trade-offs and pros/cons |
| `ART-27` | Adversarial Ingestion Sample with Embedded Prompt Injection | Security Test | 195 | English | Sanitization & injection neutralization |
| `ART-28` | Multi-Tenant Data Quarantine & Isolation Policy | Privacy Policy | 385 | English | Boundary enforcement without leakage |
| `ART-29` | Autonomous Agent Task DAG Recovery Protocol | Agent Engine | 410 | English | State machine recovery explanation |
| `ART-30` | End-to-End Multimodal Intelligence Pipeline Spec | System Spec | 530 | English | High-level executive synthesis |

---

## 3. Evaluation Criteria

For each artifact, four standardized metrics were evaluated on a 1.0 – 5.0 Likert scale by independent reviewers:

1. **Clarity (1–5):** Spoken intelligibility, absence of clutter (URLs, raw tables, markdown asterisks, bracketed citations).
2. **Naturalness (1–5):** Conversational fluency, natural rhythm, authentic anime/cute persona prosody via `dp4HJlekKt0HZFHL2jQg`.
3. **Groundedness (1–5):** Strict adherence to source facts without hallucination or unsupported claims.
4. **Usefulness (1–5):** Actionable takeaways, audience appropriateness, and cognitive bloat reduction.
