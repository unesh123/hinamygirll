# HINAA Stabilization Audit

## Architecture Found
- FastAPI backend serving as a realtime gateway and WebSocket server
- React-based frontend (Vite) for realtime rendering and state management
- LLM Provider SDK with mocked and real endpoints (CX Gateway, Gemini, OpenAI)
- ElevenLabs TTS & STT integration
- Three.js/Pixiv VRM Avatar renderer for visual presence
- Browser capabilities and tooling infrastructure
- Missing or broken tool result delivery path

## Relevant Files
- `apps/api/hinaa_api/config.py`: Environment configuration
- `apps/api/hinaa_api/main.py`: FastAPI application entrypoint
- `apps/api/hinaa_api/providers/cx_gateway.py` (assumed based on CX Gateway): CX Gateway provider
- `apps/web/src/components/ui/AvatarPresence.tsx`: Avatar orientation and rig setup
- `apps/web/src/features/automation/`: Tool executors and registries (assumed)
- `apps/web/src/features/audio/useVSeeFace.ts`: Avatar face/bone tracking
- `apps/web/src/features/companion/`: Conversation controller
- `HINAA_ANIMA_QUALITY.json`: ComfyUI workflow file

## Working Systems
- CX Gateway authentication and text streaming (tested separately, user confirms it's working but has transient errors handled gracefully)
- VRM Avatar Rendering (mostly functional, requires T-Pose fixes)
- Frontend WebSocket connection
- Basic Voice/Lipsync pipeline
- Frontend theme and layout

## Broken Systems
- Tool Result Delivery: Automation tasks execute but results do not appear in the conversation reliably
- Generic Error System: Recovers in Nepali or generic English rather than the required Roman Hindi-English
- Browser automation fallback and safety checks
- Avatar Orientation / T-Pose: Manual rotation conflicts with normalized bones, raw J_Bip writes override the humanoid rig

## Missing Components
- Robust Tool Result Envelope format
- Generic Result Renderer fallback
- Typed Error Taxonomy implementation
- ComfyUI backend provider (`LocalComfyUIProvider`)
- Ten-image safe generation queue

## Error Message Sources
- Generic `technical glitch` or `something went wrong` found in various try/catch blocks
- Nepali recovery phrases (`माफ`, `समस्या`) need auditing and replacement with Hindi-English

## ComfyUI Workflow Format
- Inspected `HINAA_ANIMA_QUALITY.json`. It is **API Format**. It contains top-level node IDs (e.g. "46", "91") with `class_type` and `inputs`, and no UI layout positions.
- Will rename to `HINAA_ANIMA_QUALITY_API.json` for clarity.

## Avatar Orientation Writers
- `apps/web/src/components/ui/AvatarPresence.tsx` contains `vrm.scene.rotation.y = Math.PI` (duplicate 180-degree rotation)
- Raw bone writes happen on `vrm.humanoid.getNormalizedBoneNode(...)` but with wrong bone names or conflicting transforms.

## Security Concerns
- Need to ensure ComfyUI endpoints are not exposed outside localhost.
- Ensure API keys are never leaked to frontend.
- Provide explicit user approval gateway for side-effecting tools.
