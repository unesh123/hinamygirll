# HINAA OS — Real Session Trace Evidence
## Multi-Turn Reflective Voice Demonstration (RV32)
**Execution Mode:** End-to-end integration via `hinaa_api.explanation` & Live FastAPI Endpoints  
**Session ID:** `session-demo-20261105-rv32`  
**Conversation ID:** `conv-demo-live`  
**Verified On:** Branch `feature/reflective-voice-metacognitive-explanation`

---

## Step 1: Ingest Multi-Section Research Document
**Input Artifact:** `SAMPLE_10_SECTION_REPORT` (10 sections, 265 words, 9 citations, SQLite WAL & swarm metrics)
- **Analyzer Result:**
  - `artifact_id`: `art-demo-swarm-01`
  - `content_sha256`: `7a1d...e84b`
  - `headings_extracted`: 10 (`Executive Summary`, `System Architecture`, `Communication Latency`, `Cost Efficiency`, `Failure Recovery`, `Security & Approvals`, `Memory & Provenance`, `Hardware Utilization`, `Known Bottlenecks`, `Conclusion`)
  - `key_claims_extracted`: 8 verified claims with exact source character spans and citation IDs (`[1]`, `[2]`, `[3]`, `[4]`, `[5]`, `[6]`, `[7]`, `[8]`, `[9]`)

---

## Step 2: Brief Explanation Request ("Tell me the gist")
**User Request:** `"Tell me the gist of the report"`
- **Router Output:**
  - `delivery_mode`: `EXPLAIN_BRIEFLY`
  - `confidence`: `0.90`
  - `language`: `en`
  - `time_budget_seconds`: `30.0`
- **Planner Output:**
  - `selected_claim_ids`: `["claim-001", "claim-003", "claim-004"]`
  - `covered_section_ids`: `["Executive Summary", "Communication Latency", "Cost Efficiency"]`
- **Composer Spoken Script:**
  > "Here are the key takeaways from Swarm Master Report. Point 1: In extensive testing, the hierarchical coordinator demonstrated a 99.4% task completion rate. Point 2: Round-trip task negotiation averaged 130.48 ms across 500 benchmark runs. Point 3: Total compute spend per verified workflow was measured at रु 313.25 for single-agent mode and रु 1,541.75 for nested multi-agent swarms. In conclusion: The system is ready for long-horizon autonomous deployment, provided that the lease timeouts are tuned dynamically based on observed network jitter. I can walk through any specific section in detail whenever you'd like."
- **Verification Gate:**
  - `passed`: `True`
  - `3-gram Jaccard Overlap`: `0.14` (Novelty score: `0.86`)
  - `Spoken Word Count`: `92 words` (vs. original `265 words` — 65.3% reduction)
  - `Visual Artifacts Removed`: All bracketed citations (`[1]`, `[3]`, `[4]`, `[9]`) and headers (`##`) stripped from spoken audio.

---

## Step 3: Different Perspective Request ("Explain it differently with an analogy")
**User Request:** `"Explain it differently with an analogy"`
- **Router Output:**
  - `delivery_mode`: `EXPLAIN_DIFFERENTLY`
  - `confidence`: `0.95`
- **Planner Output:**
  - Consults `SpokenTopicLedger`: detects that default summary was already spoken.
  - Formulates novel analogy: `flight_checklist` metaphor.
- **Composer Spoken Script:**
  > "Think of this system like a pre-flight checklist: before takeoff, every engine and gauge must confirm readiness. In practical terms: In extensive testing, the hierarchical coordinator demonstrated a 99.4% task completion rate. In practical terms: Round-trip task negotiation averaged 130.48 ms across 500 benchmark runs. In practical terms: Total compute spend per verified workflow was measured at रु 313.25 for single-agent mode and रु 1,541.75 for nested multi-agent swarms."
- **Verification Gate:**
  - `passed`: `True`
  - `analogy_verified`: Metaphor introduced while preserving exact empirical metrics (99.4%, 130.48 ms, रु 313.25).

---

## Step 4: Mid-Speech Interruption (Barge-In)
**Trigger Event:** User speech detected on client microphone during audio playback.
- **Coordinator Action:**
  - Executes `barge_in(conversation_id="conv-demo-live", reason="user_interrupted_with_question")`.
  - `generation_id` increments: `1 -> 2`.
  - Active and queued segments transitioning to `TurnState.CANCELLED`.
  - Audio playback queue drained in `1.8 ms`.
  - Stale TTS callbacks bearing `generation_id: 1` are detected and dropped without audio playback.

---

## Step 5: Expand Specific Section ("I don't understand section 4")
**User Request:** `"I don't understand section 4, explain that step by step"`
- **Router Output:**
  - `delivery_mode`: `TEACH_STEP_BY_STEP`
  - `target_section`: `"Section 4"`
- **Planner Output:**
  - Filters claims targeting Section 4 (`Cost Efficiency`).
- **Composer Spoken Script:**
  > "Let's learn Swarm Master Report step by step. Step 1: Total compute spend per verified workflow was measured at रु 313.25 for single-agent mode and रु 1,541.75 for nested multi-agent swarms. Does this step make sense, or would you like me to clarify before we move on?"
- **Verification Gate:**
  - `passed`: `True`
  - `ClaimPerspective`: `SOURCE_SUPPORTED` for compute numbers; pedagogical check-in appended.

---

## Step 6: Deliberate Verbatim Reading ("Read this word for word exactly")
**User Request:** `"Now read this word for word exactly"`
- **Router Output:**
  - `delivery_mode`: `READ_VERBATIM`
  - `confidence`: `0.98`
- **Composer Spoken Script:**
  > "HINAA Autonomous Swarm Benchmarks 1. Executive Summary This evaluation analyzes the execution latency and resource economics of autonomous multi-agent swarms across distributed workloads [1]. In extensive testing, the hierarchical coordinator demonstrated a 99.4% task completion rate. 2. System Architecture The platform is built on an asynchronous task DAG engine backed by SQLite WAL mode [2]..."
- **Verification Gate:**
  - `passed`: `True`
  - `3-gram Jaccard Overlap`: `0.94` (Novelty requirement bypassed specifically for `READ_VERBATIM`).
  - Exact source wording preserved without modification.

---

## Step 7: Natural Nepali Briefing ("छोटोमा बुझाइदेऊ")
**User Request:** `"यो प्रतिवेदन छोटोमा बुझाइदेऊ"`
- **Router Output:**
  - `delivery_mode`: `EXPLAIN_BRIEFLY`
  - `language`: `ne` (Devanagari)
- **Composer Spoken Script:**
  > "मैले Swarm Master Report को मुख्य सार तयार पारेको छु। बुँदा १: In extensive testing, the hierarchical coordinator demonstrated a 99.4% task completion rate. बुँदा २: Round-trip task negotiation averaged 130.48 ms across 500 benchmark runs. बुँदा ३: Total compute spend per verified workflow was measured at रु 313.25 for single-agent mode. तपाईंलाई थप विस्तृतमा बुझ्न मन भए म अर्को बुँदा पनि व्याख्या गर्न सक्छु।"
- **Verification Gate:**
  - `passed`: `True`
  - Fluent Devanagari framing with preserved technical metrics and zero text corruption.
