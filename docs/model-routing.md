# Model Registry, Provenance & Routing Architecture

## 1. Architectural Philosophy & Governance
HNA / HINA implements a **server-owned model registry**. Model resolution, parameter bounding, rate limiting, and fallback decisions occur exclusively on the backend (`apps/api/hinaa_api/harness/model_registry.py`). The frontend consumes validated capabilities rather than managing an unvetted client-side list of model strings.

---

## 2. Server-Owned Model Registry & Provenance Record

| Model Identifier | Provider | Declared Context Window | Declared Max Output | Modalities | Tool Calling | Metadata Source & Retrieval Timestamp | Account Access Status | Smoke Test Observed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gemini-2.5-flash` | Google | 1,048,576 | 65,536 | Text, Vision, Audio | Yes | Google AI Studio Docs (2026-10-16) | Configured when `GEMINI_API_KEY` set | Observed in harness integration suite |
| `gemini-2.5-pro` | Google | 2,097,152 | 65,536 | Text, Vision, Audio | Yes | Google AI Studio Docs (2026-10-16) | Configured when `GEMINI_API_KEY` set | Declared capability; verified in registry |
| `claude-3-7-sonnet-20250219` | Anthropic | 200,000 | 64,000 | Text, Vision | Yes | Anthropic API Documentation (2026-10-16) | Blocked without `ANTHROPIC_API_KEY` | Declared capability; schema verified |
| `llama-3.3-70b-versatile` | Groq | 128,000 | 32,768 | Text | Yes | Groq API Models Spec (2026-10-16) | Blocked without `GROQ_API_KEY` | Declared capability; schema verified |
| `gpt-4o` | OpenAI | 128,000 | 16,384 | Text, Vision, Audio | Yes | OpenAI Platform Documentation (2026-10-16) | Blocked without `OPENAI_API_KEY` | Declared capability; schema verified |
| `hinaa-mock-v1` | Local / Mock | 32,768 | 4,096 | Text | Yes | In-Repo Harness (`providers/mock.py`) | Always available (No external credentials) | Observed in unit & offline test suites |

> [!NOTE]
> **Observed vs. Declared Capabilities**: Declared context bounds are verified against official provider documentation. Observed capabilities reflect behaviors directly executed in automated local integration test suites (e.g., streaming JSON plan emission, structured tool schema parsing, and token tracking).

---

## 3. Provider Order & Trust Boundaries

The `AUTO_PRIORITY` list in [`resolveProviderSelection.ts`](file:///c:/Users/unesh/OneDrive/all%20my%20cloud%20stroge/Desktop/APPS/HINAMYGIRL/apps/web/src/features/providers/utils/resolveProviderSelection.ts) is an **operational routing sequence**, not an unsupported qualitative claim. Each entry represents a distinct provider gateway and trust boundary:

1. **`cx-gateway`**:
   - *Target*: Enterprise multi-model reverse proxy.
   - *Trust Boundary*: External HTTP gateway; requires configured `CX_GATEWAY_API_KEY` and `CX_GATEWAY_BASE_URL`.
2. **`claude`**:
   - *Target*: Anthropic API or enterprise Claude gateway.
   - *Trust Boundary*: Direct vendor API or enterprise proxy using `ANTHROPIC_API_KEY`.
3. **`experiential`**:
   - *Target*: Experiential Labs OpenAI-compatible inference proxy (`https://api.experientiallabs.ai/v1`).
   - *Trust Boundary*: Third-party managed gateway using `EXPLABS_API_KEY`.
4. **`codecraft`**:
   - *Target*: Specialized developer inference proxy.
   - *Trust Boundary*: External gateway using `CODECRAFT_API_KEY`.
5. **`real` / `gemini-live`**:
   - *Target*: Google Gemini direct endpoint via the official Google GenAI SDK.
   - *Trust Boundary*: Direct Google Cloud / Vertex AI endpoint using `GEMINI_API_KEY`.

---

## 4. Documented Routing Policy

Routing decisions are governed by a deterministic, multi-factor policy rather than arbitrary heuristics:

1. **Capability Matching**:
   - If an interaction requires visual image inspection (`requires_vision=True`), providers lacking multimodal input support are filtered out.
   - Turns requiring structured tool execution demand models supporting JSON schema tool calling.
2. **Credential Availability & Account Access**:
   - Providers with missing environment variables are treated as unconfigured and skipped during auto-routing.
3. **Health & Circuit Breaker State**:
   - A provider that experiences 3 consecutive failures within 60 seconds trips to `OPEN` for 30 seconds, routing subsequent traffic to healthy alternatives.
4. **Explicit User Selection**:
   - When a user explicitly chooses a specific model, that choice is strictly respected.
   - If the chosen model is unconfigured or encounters an outage, the system returns an honest, actionable error (`503` or `422`) rather than silently substituting an unauthorized model.
5. **Cost & Privacy Bounds**:
   - Requests are never silently escalated to a paid third-party provider if the user selected a free/local tier.
   - Fallback metadata (`requestedProvider`, `resolvedProvider`, `fallbackReason`) is always exposed in the turn payload.
