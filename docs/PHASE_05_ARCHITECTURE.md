# HINAA OS — PHASE 05 ARCHITECTURE SPECIFICATION
## MASTER AUTONOMOUS INTELLIGENCE AND ENGINEERING OPERATING ENVIRONMENT

**Document ID:** `PHASE_05_ARCHITECTURE`  
**Phase:** 05 — Singularity Evolution  
**Date:** 2026-11-12  
**System Target:** Enterprise Multimodal Autonomous Operating Environment  

---

## 1. END-TO-END SYSTEM TOPOLOGY

```mermaid
flowchart TD
    subgraph ClientLayer ["Client Layer (HINAA Studio / Web UI)"]
        UI_Shell["Workspace Shell (React / Vite)"]
        UI_Composer["Frontier Composer (200k Input / TXT Ingest)"]
        UI_Inspector["Interactive Inspector & Diagnostics"]
        UI_Studio["Motion Studio & Code Preview"]
    end

    subgraph GatewayLayer ["API Gateway & Security PDP"]
        GW_FastAPI["FastAPI 0.3.0 Engine (:8000)"]
        GW_Auth["Clerk & Local Dev Auth Context"]
        GW_PDP["Central PDP (RBAC + ABAC Policy Engine)"]
        GW_Stream["NDJSON Streaming Protocol"]
    end

    subgraph CognitiveLayer ["Cognitive Core & Orchestrator"]
        COG_Compiler["Context Compiler (Dynamic Token Budgeting)"]
        COG_Router["Resilient Model Router (Circuit Breakers)"]
        COG_State["Dialogue State & Intent Classifier"]
        COG_Memory["Episodic & Procedural Memory Service"]
    end

    subgraph ExecutionLayer ["Autonomous Execution Harness"]
        HAR_Master["Master Orchestrator Agent"]
        HAR_Specialists["10 Specialist Agents (Frontend, Backend, QA, etc.)"]
        HAR_Tools["Unified Tool Registry (Timeouts, Audits, QC)"]
        HAR_StateMachine["AgentRun State Machine (Checkpoints & Recovery)"]
    end

    subgraph RuntimeLayer ["Isolated Sandbox & Workspace Environment"]
        RT_Git["Git Worktrees & Branch Isolation"]
        RT_Sandbox["Container / Process Sandbox Adapter"]
        RT_Terminal["Terminal Hands & PTY Session"]
        RT_Browser["Browser Agent & CDP Automation"]
    end

    subgraph MediaLayer ["Multimodal & Motion Studio Engine"]
        MED_Ingest["Universal File Ingestion (30+ Formats)"]
        MED_Video["Video Analyzer (Keyframes & Scene Detection)"]
        MED_Renderer["Deterministic FFmpeg 7.1 Video Compositor"]
        MED_Docs["Document Publisher (PDF, DOCX, PPTX)"]
    end

    subgraph PersistenceLayer ["Durable Persistence & Storage"]
        DB_SQL["SQL Database (SQLite / Postgres ORM)"]
        DB_Ledger["Brain Ledger & Circuit State"]
        DB_Artifacts["Artifact & Document Asset Store"]
    end

    UI_Composer --> GW_FastAPI
    UI_Shell --> GW_FastAPI
    GW_FastAPI --> GW_Auth --> GW_PDP
    GW_PDP --> COG_Compiler
    COG_Compiler --> COG_Router
    COG_Router --> HAR_Master
    HAR_Master --> HAR_Specialists
    HAR_Specialists --> HAR_Tools
    HAR_Tools --> HAR_StateMachine
    HAR_StateMachine --> RT_Git
    HAR_StateMachine --> RT_Sandbox
    HAR_StateMachine --> RT_Terminal
    HAR_StateMachine --> RT_Browser
    HAR_Specialists --> MED_Renderer
    HAR_Specialists --> MED_Docs
    MED_Ingest --> COG_Compiler
    HAR_StateMachine --> DB_SQL
    GW_FastAPI --> DB_Ledger
    MED_Docs --> DB_Artifacts
```

---

## 2. ADVANCED COGNITIVE INTELLIGENCE CORE (WORKSTREAM 01)

### 2.1 Dynamic Context Budgeting
Modern frontier models offer vastly different context capacities:
- **Ultra-Long (1M Tokens):** `gemini-3.5-flash` (~4,000,000 characters).
- **Extended (200k Tokens):** `claude-opus-5.5`, `claude-sonnet-4-6` (~800,000 characters).
- **Standard (128k Tokens):** `mistralai/codestral-2508`, `deepseek-v4.1-flash` (~512,000 characters).
- **Local / Edge (8k–32k Tokens):** Local models and fast intent gates.

The `ContextCompiler` dynamically retrieves the active model's token limits and allocates budgets across priority layers:

$$\text{Total Budget} = \text{Model Context Window} - \text{Max Output Tokens} - \text{Safety Margin}$$

```mermaid
flowchart LR
    Total["Total Context Budget"] --> System["System Policy (15%)"]
    Total --> Memory["Approved Memory (15%)"]
    Total --> Documents["Attached Files & Code RAG (40%)"]
    Total --> History["Conversation History (15%)"]
    Total --> User["User Objective (15%)"]
```

### 2.2 Layer Priority & Trusted Delimiters
Content is partitioned by security trust boundaries:
1. **Priority 0 (Trusted Application):** System Persona, Core Safety Rules, Output Contracts.
2. **Priority 5 (Application Verified):** Model Metadata, Capability Flags, Tool Definitions.
3. **Priority 8 (Trusted Application):** Approved Long-Term Memory, Verified User Profile.
4. **Priority 10 (Untrusted Data):** Attached Documents, Web Search Snippets, RAG Chunks.
5. **Priority 15 (Untrusted History):** Prior Conversational Turns.
6. **Priority 20 (Untrusted User Content):** Current User Prompt and Instructions.

Untrusted blocks are strictly wrapped with `<attached_documents trusted="false">` and `<user_message trusted="false">` delimiters to prevent prompt injection from overriding core safety invariants.

---

## 3. AUTONOMOUS AGENT HARNESS & EXECUTION STATE MACHINE (WORKSTREAM 02 & 05)

### 3.1 Durable Agent State Machine

```mermaid
stateDiagram-v2
    [*] --> CREATED
    CREATED --> PLANNING : Initialize Objective
    PLANNING --> AWAITING_APPROVAL : Generate Step Plan
    AWAITING_APPROVAL --> RUNNING : User / Policy Approved
    AWAITING_APPROVAL --> CANCELLED : Rejected
    RUNNING --> CHECKPOINTING : Step Completed
    CHECKPOINTING --> RUNNING : Persist State to DB
    RUNNING --> WAITING_FOR_USER : Clarification / Secret Required
    WAITING_FOR_USER --> RUNNING : Input Received
    RUNNING --> VERIFYING : All Steps Executed
    VERIFYING --> COMPLETE : QC / Tests Passed
    VERIFYING --> REPAIR : Test / Lint Failed
    REPAIR --> RUNNING : Re-attempt with Fix
    RUNNING --> PAUSED : User Pause Request
    PAUSED --> RUNNING : Resume
    RUNNING --> FAILED : Unrecoverable Error / Budget Exceeded
    COMPLETE --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

### 3.2 Specialist Agent Hierarchy
1. **Master Orchestrator:** Decomposes macro goals, schedules sub-agent dependencies, monitors token/time budgets, handles user approval requests.
2. **Research Agent:** Performs multi-hop Exa and live web search, summarizes academic papers, collects reference datasets.
3. **Frontend Engineering Agent:** React, Vite, TypeScript, Tailwind, WebGL component development and CSS responsive styling.
4. **Backend Engineering Agent:** FastAPI, Python, database queries, ORM migrations, async background tasks.
5. **Database Agent:** Schema design, SQL index optimization, Alembic migrations, data validation.
6. **Testing and QA Agent:** Pytest, Vitest, Playwright automated testing, regression checking, coverage verification.
7. **Security Review Agent:** Secret scanning, dependency vulnerability audit, authorization boundaries, sanitization checks.
8. **Documentation Agent:** API reference generation, README documentation, architecture diagrams, user manuals.
9. **Creative Director Agent:** Aesthetic design, typography, color palettes, visual mood boards, animation timing sheets.
10. **Media Production Agent:** FFmpeg command synthesis, video keyframe analysis, audio normalization, render job verification.

---

## 4. UNIVERSAL FILE INTELLIGENCE ARCHITECTURE (WORKSTREAM 06)

```mermaid
flowchart TD
    Upload["Raw File Upload / Reference"] --> Detection["Magic Byte & MIME Signature Detection"]
    
    Detection --> PDF["PDF Parser (pypdf Page Extraction)"]
    Detection --> Office["Office Parser (DOCX XML / XLSX Sheets / PPTX XML)"]
    Detection --> Code["Code Parser (Tree-sitter / Pygments Syntax Index)"]
    Detection --> Media["Media Parser (FFmpeg Audio WAV / Video Keyframes)"]
    Detection --> Archive["Archive Inspector (Safe ZIP/TAR Directory Tree)"]

    PDF --> Extracted["Structured Text & Metadata"]
    Office --> Extracted
    Code --> Extracted
    Media --> Extracted
    Archive --> Extracted

    Extracted --> SecurityCheck{"Secret & PII Scanner"}
    SecurityCheck -- Pass --> Indexer["Semantic Vector & Lexical Inverted Index"]
    SecurityCheck -- Detected --> Redactor["Redact Keys / Tokens & Log Audit"] --> Indexer
    Indexer --> PromptContext["Context Compiler (Attached Document Injection)"]
```

---

## 5. HINA MOTION STUDIO: OPEN VIDEO ENGINE (WORKSTREAM 07)

### 5.1 Architecture & Stack Choice
To eliminate commercial licensing restrictions associated with proprietary frameworks like Remotion, HINA Motion Studio implements a **fully open, royalty-free composition and rendering architecture**:

```mermaid
flowchart LR
    Timeline["TimelineSpec (JSON)"] --> SceneEngine["Three.js / HTML Canvas / SVG Engine"]
    SceneEngine --> HeadlessChrome["Puppeteer / Chrome Headless (Frame Buffer)"]
    AudioEngine["Audio Spec (LUFS -14.0)"] --> FFmpegMixer["FFmpeg 7.1 Multiplexer"]
    HeadlessChrome --> FFmpegMixer
    FFmpegMixer --> MasterMP4["Verified MP4 (H.264 / AAC)"]
    MasterMP4 --> QCGate{"Automated QC Gate"}
    QCGate -- "Pass (Zero drop, Audio sync)" --> OutputArtifact["Final Deliverable (preview.mp4 / master.mp4)"]
    QCGate -- Fail --> ErrorLog["Render Exception Log"]
```

### 5.2 Video Reference Understanding Pipeline
When a user uploads a reference video:
1. **Probe Stream:** Inspect resolution, duration, framerate, video/audio codecs via `ffprobe`.
2. **Keyframe Extraction:** Extract scene change frames using `ffmpeg -i video.mp4 -vf "select='gt(scene,0.4)',scale=960:-1" -vsync vfr frames/%04d.png`.
3. **Audio Extraction & Beat Mapping:** Extract 16 kHz WAV audio, estimate BPM and transient beats via signal peak detection.
4. **Reference Package:** Package keyframes, scene timings, color palettes, and motion curves into a structured JSON manifest for model ingestion.

---

## 6. GITHUB-NATIVE INTEGRATION ARCHITECTURE (WORKSTREAM 03)

```mermaid
sequenceDiagram
    participant User as User / Operator
    participant Agent as HINAA Agent Harness
    participant Worktree as Local Git Worktree
    participant GitHub as Remote GitHub API

    User->>Agent: "Implement issue #42: Add token rate limiter"
    Agent->>GitHub: Fetch Issue #42 Details & Comments
    Agent->>Worktree: Create isolated branch 'feature/issue-42-rate-limiter'
    Agent->>Worktree: Read codebase files & dependencies
    Agent->>Worktree: Modify code & write unit tests
    Agent->>Worktree: Run pytest / vitest in sandbox
    Worktree-->>Agent: Tests pass with 0 errors
    Agent->>Worktree: Create git commit with signed commit message
    Agent->>GitHub: Push branch to origin
    Agent->>GitHub: Open Pull Request with summary & test evidence
    GitHub-->>User: Pull Request ready for human review
```

---

## 7. SECURITY & AUTHORIZATION POLICY (WORKSTREAM 11)

### 7.1 Multi-Tier Action Risk Matrix

| Risk Tier | Classification | Description | Permitted Authorization Source |
|---|---|---|---|
| **Tier 0** | Read-Only | Observation, `system_info`, inspecting directories, reading code | Inherent / Standing Consent |
| **Tier 1** | Reversible | Workspace temp folder creation, local scratch edits | Bounded Workspace Policy |
| **Tier 2** | External | Web navigation, file downloads, external documentation queries | Confirmed User or Scoped Role |
| **Tier 3** | Process Exec | Terminal command execution, process spawning, code evaluation | **Strictly Confirmed User (`approval_source='user'`)** |
| **Tier 4** | Destructive / Irreversible | Git force-push, production deployment, external payments, deletion | **Strictly Authenticated Owner + Explicit Confirmation** |

### 7.2 Core Authorization Invariant
$$\text{Permission Granted} \iff \text{Token Valid} \land \text{User ID Authenticated} \land \text{Role Has Perm}(\text{Action}) \land \neg\text{Emergency Stop}$$

No client-supplied JSON header or query parameter can independently bypass PDP evaluation.
