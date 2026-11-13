# HINAA OS — REMAINING IMPLEMENTATION ROADMAP
**Audit Date:** 2026-11-12  
**Target Horizon:** Phase 06 Finalization & Production Deployment  
**Auditor:** Antigravity Master Engineering & Verification Engine  
**Status:** ACTIVE_ROADMAP  

---

## 1. Executive Summary

Having verified the core operating system architecture across Phase 01–06 (including the 200K large input pipeline, Persona Prime, Memory Nexus, Computer Operator reality, frontend Vitest suite, and SQLite WAL database), this roadmap defines the concrete, prioritized engineering workstreams required to bridge remaining external dependencies and production operations.

---

## 2. Prioritized Engineering Workstreams

### Workstream 1: External Credential & Upstream Provisioning (Priority: High)
*Objective: Unblock live third-party cloud integrations that are implemented in code but gated by external credentials or billing.*

1. **ElevenLabs TTS Quota & Voice Key:**
   - Verify user-provided ElevenLabs API key has active character quota.
   - Configure custom Aisha / HINA cloned voice identifier in `.env`.
   - Ensure WebSocket streaming fallback operates seamlessly if quota is depleted.
2. **GMI Gateway Lane Resolution:**
   - Investigate HTTP 402 (Payment Required) observed on `deepseek-ai/deepseek-v4.1-flash-1017`.
   - Update upstream billing or re-point gateway to active model lane.
3. **GitHub Remote Push & PR Automation:**
   - Wire user GitHub Personal Access Token (`GITHUB_TOKEN`) with `repo` and `workflow` scopes.
   - Enable automated branch creation, commit signing, and pull request generation from the Core Developer subagent.
4. **Microsoft Outlook & Graph OAuth:**
   - Complete Azure AD App Registration for Microsoft Graph API (`Mail.ReadWrite`, `Calendars.ReadWrite`).
   - Enable authenticated email drafting and calendar appointment booking.

---

### Workstream 2: Local & Generative Synthesis Integrations (Priority: Medium)
*Objective: Solidify multimodal generation without introducing fragile external dependencies.*

1. **Local ComfyUI Daemon Auto-Discovery:**
   - Implement health check on `http://127.0.0.1:8188/system_stats`.
   - Package standard SDXL / Flux checkpoint workflow for zero-configuration local image generation.
2. **Unified Image Fallback Provider:**
   - Graceful fallback ladder: Local ComfyUI -> OpenAI DALL-E 3 -> Fal.ai -> Generative SVG/HTML canvas.
3. **Generative Video Synthesis Architecture:**
   - Design async polling queue for Runway Gen-3 / Luma Dream Machine / Sora APIs.
   - Clearly delineate video generation as an optional cloud extension rather than a local runtime requirement.

---

### Workstream 3: Multilingual & Phoneme Alignment (Priority: Medium)
*Objective: Perfect Nepali and Hindi conversational fluency and lip-sync precision.*

1. **Devanagari Viseme Alignment:**
   - Refine phonetic mapping from Devanagari conjunct characters (`क्ष`, `त्र`, `ज्ञ`) to 3D VRM blendshapes.
2. **Multilingual VAD Tuning:**
   - Calibrate silence thresholds to accommodate cadence variations in conversational Nepali and Hindi.

---

### Workstream 4: Production Container & Cluster Deployment (Priority: Standard)
*Objective: Single-command deployment for cloud VPS or local homelab.*

1. **Docker Multi-Stage Build:**
   - Stage 1: Build React 19 frontend into static production assets.
   - Stage 2: Install Python 3.14 dependencies with wheel caching.
   - Stage 3: Minimal distroless runtime container exposing port 8000.
2. **Automated Health & Telemetry Watchdog:**
   - Script recurring readiness probes and automatic Uvicorn worker restarts upon memory threshold breach.

---

## 3. Implementation Timeline

| Workstream | Target Milestone | Primary Subsystem | Complexity |
| :--- | :--- | :--- | :--- |
| **1. Upstream Auth & GitHub** | Sprint 1 (Immediate) | `hinaa_api/integrations/` | Low (Env/Token setup) |
| **2. ComfyUI Local Pipeline** | Sprint 1 | `hinaa_api/generation/` | Medium (Workflow parsing) |
| **3. Devanagari Visemes** | Sprint 2 | `apps/web/src/components/avatar/` | Medium (WebGL morph targets) |
| **4. Dockerized Cluster** | Sprint 2 | Root `docker-compose.yml` | Low (Container manifest) |

---

## 4. Conclusion

This roadmap provides a transparent, actionable path forward. By addressing external credentials and containerization, HINAA OS transitions from a verified local development environment into a fully provisioned, production-grade AI operating platform.
