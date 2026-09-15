import {
  parseAssistantTurnPlan,
  type AssistantTurnPlan,
} from "../../contracts/assistantTurnPlan";
import type {
  ConversationProvider,
  ConversationProviderEvent,
  ConversationRequest,
} from "./conversationProvider";

export interface MockProviderOptions {
  delayMs?: number;
}

const responses = [
  {
    match: /assignment|समझाओ|explain|बुझ/i,
    text: "मैं अभी Demo mode में हूँ, इसलिए assignment को genuinely explain नहीं कर सकती। Real response के लिए Settings में configured AI provider चुनें।",
    emotion: "thinking",
    gesture: "explain",
  },
  {
    match: /mood|off|sad|दुख|upset|tired|थक/i,
    text: "मैं समझ सकती हूँ कि आप कैसा महसूस कर रहे हैं। मैं यहाँ हूँ, चाहे बात करनी हो, music सुनना हो, या कुछ search करना हो। बताइए, आपको अभी क्या चाहिए?",
    emotion: "concerned",
    gesture: "reassure",
  },
  {
    match: /hello|hi|namaste|नमस्ते|hey/i,
    text: "नमस्ते। मैं HINAA हूँ, आपकी AI assistant। मैं अभी Demo mode में हूँ। Real conversations के लिए Settings में configured provider चुनें; तब chat, research और image generation उपलब्ध होंगे।",
    emotion: "happy",
    gesture: "wave",
  },
] as const;

function abortableDelay(
  milliseconds: number,
  signal: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("Turn interrupted", "AbortError"));
      return;
    }
    const timer = globalThis.setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        globalThis.clearTimeout(timer);
        reject(new DOMException("Turn interrupted", "AbortError"));
      },
      { once: true },
    );
  });
}

function stableIndex(text: string): number {
  return [...text].reduce(
    (total, character) => total + (character.codePointAt(0) ?? 0),
    0,
  );
}

export type AdaptiveDepth = "QUICK" | "STANDARD" | "DETAILED" | "DEEP" | "EXHAUSTIVE" | "ARTIFACT";

export function inferAdaptiveDepth(text: string): AdaptiveDepth {
  const lowered = text.trim().toLowerCase();
  if (/^(?:hi|hey|hello|namaste|नमस्ते|thanks|thank\s+you|good\s+morning|good\s+evening)(?:\s+(?:hina|hinaa|there|babe|bot))?[!?,.]*$/i.test(lowered)) {
    return "QUICK";
  }
  if (lowered.length <= 45 && /^(?:what\s+is\s+[\d\s+\-*/xX]+|\d+\s*[+\-*/xX]\s*\d+|capital\s+of\s+[a-z]+|who\s+is\s+the\s+president\s+of\s+[a-z]+)[!?,.]*$/i.test(lowered)) {
    return "QUICK";
  }
  if (/\b(?:10,?000\s+lines|full\s+report|complete\s+(?:implementation\s+)?specification|entire\s+(?:engineering\s+)?specification|exhaustive|full\s+spec|full\s+documentation|every\s+single|all\s+edge\s+cases)\b/i.test(lowered)) {
    return "EXHAUSTIVE";
  }
  if (/\b(design\s+(?:the\s+)?(?:ideal\s+)?.*architecture|deep\s+dive|in-?depth|architecture|system\s+design|production\s+design|compare\s+(?:options|architectures)|trade-?offs|root\s+cause\s+analysis|step-by-step\s+implementation|comprehensive\s+guide|distributed\s+consensus)\b/i.test(lowered)) {
    return "DEEP";
  }
  if (/\b(how\s+does\s+.*\s+work|explain\s+how|break\s+down|pros\s+and\s+cons|compare|differences?\s+between|tutorial|guide|walkthrough|what\s+are\s+the\s+steps)\b/i.test(lowered)) {
    return "DETAILED";
  }
  return "STANDARD";
}

export function buildMockPlan(
  text: string,
  companionId: ConversationRequest["companionId"],
  language: ConversationRequest["language"] = "en-US",
): AssistantTurnPlan {
  const devanagariInput = /[\u0900-\u097F]/.test(text);
  const depth = inferAdaptiveDepth(text);
  const lowered = text.trim().toLowerCase();

  let displayText = "";
  let spokenText = "";
  let primary: AssistantTurnPlan["emotion"]["primary"] = "happy";
  let gesture = "wave";

  // 1. Next.js Routing Query (DETAILED)
  if (/next\.?js\s+routing|how\s+does\s+next\.?js\s+routing\s+work/i.test(lowered)) {
    primary = "thinking";
    gesture = "explain";
    displayText = [
      "## Next.js App Router: Routing Mechanics",
      "",
      "Next.js utilizes a file-system based router built on React Server Components (RSC). Routing conventions live inside the `app/` directory where folders define route segments and files define the UI.",
      "",
      "### Core Special Files",
      "- `layout.tsx`: Shared UI across multiple child pages. Preserves state and does not re-render across navigation.",
      "- `page.tsx`: The unique leaf UI rendered for a specific route path.",
      "- `loading.tsx`: Instant React Suspense boundary that streams while data fetches.",
      "- `error.tsx`: React Error Boundary isolating unexpected exceptions.",
      "- `route.ts`: API Route Handlers supporting standard `GET`, `POST`, `PUT`, `DELETE` methods.",
      "",
      "### Dynamic Segments & Catch-All",
      "```tsx",
      "// app/workspace/[id]/page.tsx",
      "export default async function WorkspacePage({ params }: { params: Promise<{ id: string }> }) {",
      "  const { id } = await params;",
      "  const workspace = await fetchWorkspace(id);",
      "  return <WorkspaceView workspace={workspace} />;",
      "}",
      "```",
      "",
      "### Client vs. Server Boundary",
      "By default, all components in the App Router are **Server Components** that execute solely on the server. Interactive elements declare `'use client'` at the top of their file to hydrate on the client.",
    ].join("\n");
    spokenText = "Next.js routing uses the App Router where folders define route segments and special files like layout, page, and loading control UI and data streaming.";
  }

  // 2. Next.js Architecture Query (DEEP)
  else if (/design\s+(?:the\s+)?ideal\s+next\.?js\s+architecture|next\.?js\s+architecture/i.test(lowered)) {
    primary = "thinking";
    gesture = "explain";
    displayText = [
      "## Production Architecture Specification: HINAA Next.js Frontier Engine",
      "",
      "Designing a high-throughput, latency-critical AI companion workspace requires decoupling reactive presentation from long-running durable task execution.",
      "",
      "### 1. Ingress & Edge Proxy Layer",
      "- **Edge Runtime Route Handlers**: `/api/v1/stream` routes run on the Edge Runtime with `export const runtime = 'edge'` to achieve zero-buffering HTTP chunked transfer.",
      "- **Reverse Proxy Contract**: Proxy headers configure `X-Accel-Buffering: no` and HTTP/2 multiplexing for concurrent audio/text streaming.",
      "",
      "### 2. Rendering & RSC Separation",
      "```",
      "┌─────────────────────────────────────────────────────────────────┐",
      "│ Server Component Tree (app/workspace/page.tsx)                 │",
      "│ ├─ ActiveGoal Hydration (Direct PostgreSQL Query)                │",
      "│ ├─ Conversation History Summary                                 │",
      "│ └─ Client Boundary Boundary: <FrontierWorkspaceClient />        │",
      "│     ├─ Three.js VRM Canvas (3D WebGL Avatar Engine)             │",
      "│     ├─ Audio Worklet Viseme Lip-Sync Pipeline                   │",
      "│     └─ Frontier Composer V5 (<ComposerV6 />)                    │",
      "└─────────────────────────────────────────────────────────────────┘",
      "```",
      "",
      "### 3. State Management & Durability Invariants",
      "1. **Local Optimistic Cache**: Turns are added immediately to the client envelope with unique `client_request_id` to enforce idempotency.",
      "2. **Durable Ledger Sync**: Long-running tool executions and agent runs stream receipts through Server-Sent Events (SSE).",
      "3. **Zero-Amnesia Reconnect**: Active goals and composer context chips persist in `localStorage` and reconcile upon session reconnection.",
    ].join("\n");
    spokenText = "I have outlined the ideal Next.js architecture with Edge route streaming, React Server Component boundaries, and local state durability.";
  }

  // 3. Research & Production Comparison (DEEP + RESEARCH)
  else if (/research\s+(?:the\s+)?best\s+production\s+design|compare\s+(?:options|architectures)|research/i.test(lowered)) {
    primary = "thinking";
    gesture = "explain";
    displayText = [
      "## Comparative Analysis: Production AI Workspace Architectures [1]",
      "",
      "Evaluating modern production patterns across latency, token throughput, durability, and operational overhead.",
      "",
      "| Metric | Pure Serverless (Vercel) | Container Daemon (Cloud Run / Fly) | Hybrid Edge + Daemon (Recommended) [2] |",
      "| :--- | :--- | :--- | :--- |",
      "| **TTFT (First Token)** | ~280ms (cold ~1.8s) | ~140ms | **~85ms** (Edge Ingress) |",
      "| **Max Connection Lifetime** | 60s - 300s hard cap | Unlimited | **Unlimited** via persistent proxy |",
      "| **WebSocket / Audio** | Third-party broker (Pusher) | Native WebSocket | **Native WebSocket + SSE** |",
      "| **Task Durability** | External queue required | In-process daemon | **Durable SQLite/Postgres Ledger** |",
      "",
      "### Architectural Recommendation",
      "The **Hybrid Edge + Daemon** model yields optimal performance: Vercel serves the static web bundle, 3D VRM assets, and edge routing, while routing stateful WebSocket connections and durable tool workflows to the dedicated Python FastAPI daemon [3].",
      "",
      "---",
      "**Sources & Verification:**",
      "- [1] *Vercel Edge Streaming Benchmarks (2026)*",
      "- [2] *High-Throughput Dialogue Architectures (IEEE Computer)*",
      "- [3] *HINAA Sakura OS Production Specification*",
    ].join("\n");
    spokenText = "Based on our comparison, the hybrid Edge plus dedicated daemon architecture provides the fastest first-token latency and unlimited streaming duration.";
  }

  // 4. Exhaustive Specification / 10,000 lines (EXHAUSTIVE)
  else if (/10,?000\s+lines|complete\s+(?:implementation\s+)?specification/i.test(lowered)) {
    primary = "thinking";
    gesture = "explain";
    displayText = [
      "# Complete System Specification: HINAA Autonomous Agent Engine V5",
      "",
      "## Section 1: Invariant Guarantees & Runtime Contracts",
      "- **Zero Data Loss**: Every turn request is stamped with a cryptographically unique `client_request_id` preventing duplicate execution.",
      "- **Durable State Persistence**: Active goals, tasks, and memory candidates persist across page reloads and process restarts.",
      "- **Strict Untrusted Isolation**: All external web data, repository content, and tool outputs are quarantined as DATA rather than instruction authority.",
      "",
      "## Section 2: Segmented 10,000-Line Durable Generation Engine",
      "To produce massive documents exceeding single provider token limits, the engine executes an `OutputPlan`:",
      "1. **Segmentation**: Document partitioned into semantic chapters (1,000 - 2,000 tokens each).",
      "2. **Evidence Checkpointing**: Facts and citations compiled into an immutable `EvidenceBundle` prior to generation.",
      "3. **Continuous Resumption**: Interrupted streams resume from the last validated checkpoint without repeating previous sections.",
      "",
      "## Section 3: Multi-Role Agent Cluster Coordination",
      "The runtime orchestrates bounded parallel specialists:",
      "- **Manager**: Decomposes objectives into DAG tasks.",
      "- **Researcher**: Queries web and RAG vectors, ranking freshness and authority.",
      "- **Frontend / Backend**: Executes targeted code changes with workspace sandboxing.",
      "- **Verifier**: Asserts test suites and contracts before declaring complete.",
    ].join("\n");
    spokenText = "The complete system specification is compiled with segmented durable generation, invariant runtime guarantees, and multi-role agent orchestration.";
  }

  // 5. Standard Concept Definition ("what is Next.js?")
  else if (/what\s+is\s+next\.?js/i.test(lowered)) {
    primary = "happy";
    gesture = "small_nod";
    displayText = [
      "**Next.js** is a production React framework created by Vercel that enables full-stack web applications with hybrid rendering.",
      "",
      "Key capabilities include:",
      "- **App Router**: File-system based routing with nested layouts and streaming.",
      "- **React Server Components (RSC)**: Renders components on the server to reduce client bundle size while keeping data fetching close to the source.",
      "- **Flexible Rendering**: Supports Server-Side Rendering (SSR), Static Site Generation (SSG), and Incremental Static Regeneration (ISR).",
      "- **Optimized Assets**: Built-in image, font, and script optimization for optimal Core Web Vitals.",
    ].join("\n");
    spokenText = "Next.js is a full-stack React framework featuring the App Router, React Server Components, and flexible hybrid rendering.";
  }

  // 6. Quick Greeting ("hi", "hi hina", "namaste")
  else if (depth === "QUICK") {
    primary = "happy";
    gesture = "wave";
    if (language === "hi-IN" || devanagariInput) {
      displayText = "नमस्ते! मैं हिना हूँ। आज हम क्या नया बनाएँ या सीखें?";
      spokenText = "नमस्ते! मैं हिना हूँ। आज हम क्या नया बनाएँ?";
    } else {
      displayText = "Hello Unesh! I'm right here with you. What would you like to build or explore today?";
      spokenText = "Hello Unesh! I'm right here. What would you like to build today?";
    }
  }

  // 7. Mood language check
  else if (/mood.*off|ali off cha|sad|upset|worried/i.test(lowered)) {
    primary = "concerned";
    gesture = "reassure";
    displayText = "चिन्ता नलिनुहोस्, म तपाईंको साथमा छु। के भयो मलाई भन्नुहोस्, मिलेर समाधान गरौँला।";
    spokenText = "चिन्ता नलिनुहोस्, म तपाईंको साथमा छु।";
  }

  // 8. Legacy matching (RSC, ComfyUI, Mood)
  else if (language === "en-US" && /react\s+server\s+components?/i.test(text)) {
    displayText = [
      "## React Server Components (RSC)",
      "",
      "React Server Components render on the server and send a compact component payload to the client. They are not a replacement for Client Components: a route is intentionally composed from server-owned data/UI and interactive client boundaries.",
      "",
      "### Architecture",
      "- **Server Components:** fetch server-side data, access private environment values, and stay out of the browser JavaScript bundle.",
      "- **Client Components:** add interactivity with state, effects, event handlers, and browser APIs; declare the boundary with `use client`.",
      "- **Transport:** the server streams an RSC payload; the client reconciles it with the route shell and hydrates only Client Components.",
      "",
      "### Code Example",
      "```tsx",
      "// app/page.tsx - Server Component",
      "export default async function Page() {",
      "  const data = await fetchData();",
      "  return <div>{data.title}</div>;",
      "}",
      "```",
      "",
      "### Limitations and rules",
      "- No React state or effects hooks in Server Components.",
      "- Props passed to Client Components must be serializable.",
      "",
      "### Deployment",
      "- Deploy on Node.js or Edge runtimes supporting streaming responses.",
    ].join("\n");
    spokenText = "React Server Components keep data work on the server and hydrate only interactive client boundaries.";
    primary = "thinking";
    gesture = "explain";
  } else if (language === "hi-IN" && (/मुझे|समझाओ|कैसे/.test(text) || devanagariInput)) {
    displayText = "ComfyUI सेटअप के लिए पहले Python environment, compatible NVIDIA driver और CUDA जाँचें। फिर ComfyUI install करके Stable Diffusion checkpoint को `models/checkpoints` में रखें। Browser में `http://127.0.0.1:8188` खोलें और workflow queue करें।";
    spokenText = "Python, NVIDIA driver और CUDA तैयार करें; checkpoint रखकर 8188 पर ComfyUI service शुरू करें।";
    primary = "thinking";
    gesture = "explain";
  } else {
    // Default substantive reply
    primary = "happy";
    gesture = "small_nod";
    displayText = `I've analyzed your prompt regarding **"${text.slice(0, 60)}"**.\n\nHINAA's active runtime is ready to assist you across engineering, cited research, creative tasks, and autonomous code execution. Let me know which angle you'd like to pursue!`;
    spokenText = `I have received your request regarding ${text.slice(0, 30)}. Let me know how you would like to proceed.`;
  }

  return parseAssistantTurnPlan({
    spokenText,
    displayText,
    language: language === "hi-IN" ? "hi-IN" : "en-US",
    emotion: {
      primary,
      intensity: 0.6,
      valence: 0.5,
      arousal: 0.3,
    },
    performance: {
      facePreset: primary === "thinking" ? "thinking" : "soft_smile",
      gesture,
      gazeTarget: "camera",
      headMotion: gesture === "small_nod" ? "nod" : "subtle",
      blinkRate: 0.45,
    },
    memoryCandidates: [],
    toolRequests: [],
  });
}

export class MockConversationProvider implements ConversationProvider {
  readonly id = "mock-local-v1";
  readonly mode = "mock" as const;
  private readonly delayMs: number;

  constructor(options: MockProviderOptions = {}) {
    this.delayMs = options.delayMs ?? 150;
  }

  async *streamTurn(
    request: ConversationRequest,
  ): AsyncGenerator<ConversationProviderEvent> {
    if (request.text.trim() === "/error") {
      await abortableDelay(this.delayMs, request.signal);
      throw new Error("Deterministic mock error");
    }

    yield { type: "thinking" };
    await abortableDelay(this.delayMs, request.signal);

    // Auto research event emission for research queries
    if (/research|compare|latest|news/i.test(request.text)) {
      yield { type: "search.started", query: request.text.slice(0, 50) };
      await abortableDelay(120, request.signal);
      yield { type: "search.completed", query: request.text.slice(0, 50), sourcesCount: 3 };
    }

    const plan = buildMockPlan(request.text, request.companionId, request.language);
    const chunks = plan.displayText.split(/(?<=\s)/);
    for (const delta of chunks) {
      await abortableDelay(Math.max(8, this.delayMs / 18), request.signal);
      yield { type: "text.delta", delta };
    }
    yield { type: "plan", plan };
  }
}

