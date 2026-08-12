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
    text: "Main abhi mock mode mein hoon, isliye main assignment ko genuinely explain nahi kar sakti. Real response ke liye aap real provider mode enable kar sakte ho — jaise Gemini ya OpenAI brain. Settings mein jaake provider select karo.",
    emotion: "thinking",
    gesture: "explain",
  },
  {
    match: /mood|off|sad|दुख|upset|tired|थक/i,
    text: "Main samajh sakti hoon ki aap kaisa feel kar rahe ho. Main yahaan hoon aapke liye — chahe baat karni ho, music sun na ho, ya kuch search karna ho. Just tell me what you need.",
    emotion: "concerned",
    gesture: "reassure",
  },
  {
    match: /hello|hi|namaste|नमस्ते|hey/i,
    text: "Namaste! Main HINAA hoon — aapki AI assistant. Main abhi mock mode mein hoon. Real conversations ke liye aap Settings mein jaake Gemini ya OpenAI brain select kar sakte ho. Tab main real-time web search, image generation, aur bahut kuch kar paungi.",
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

export function buildMockPlan(
  text: string,
  companionId: ConversationRequest["companionId"],
): AssistantTurnPlan {
  const professional = /react\s+server\s+components?/i.test(text)
    ? {
        language: "en-US" as const,
        displayText: [
          "## React Server Components (RSC)",
          "",
          "React Server Components render on the server and send a compact component payload to the client. They are not a replacement for Client Components: a route is intentionally composed from server-owned data/UI and interactive client boundaries.",
          "",
          "### Architecture",
          "- **Server Components:** fetch server-side data, access private environment values, and stay out of the browser JavaScript bundle.",
          "- **Client Components:** add interactivity with state, effects, event handlers, and browser APIs; declare the boundary with `use client`.",
          "- **Transport:** the server streams an RSC payload; the client reconciles it with the route shell and hydrates only Client Components.",
          "",
          "### Minimal pattern",
          "```tsx",
          "// app/products/page.tsx — Server Component by default",
          "import AddToCart from './AddToCart';",
          "export default async function ProductsPage() {",
          "  const products = await db.product.findMany();",
          "  return products.map((product) => <AddToCart key={product.id} product={product} />);",
          "}",
          "",
          "// app/products/AddToCart.tsx",
          "'use client';",
          "export default function AddToCart({ product }: { product: { id: string } }) {",
          "  return <button onClick={() => addToCart(product.id)}>Add to cart</button>;",
          "}",
          "```",
          "",
          "### Limitations and rules",
          "Server Components cannot use browser APIs, state/effect hooks, or event handlers. Props crossing into a Client Component must be serializable, and server/client imports must respect the boundary. Do not pass secrets or database clients to Client Components.",
          "",
          "### Tests",
          "Unit-test server-side data and rendering with mocked services, test Client Components in a DOM environment, and add an integration test for loading, error, and streamed route states. Verify the production bundle to ensure server-only modules are excluded from client chunks.",
          "",
          "### Deployment",
          "Deploy to a framework/runtime that supports the React Server Components protocol, keep server secrets in the deployment environment, configure caching deliberately, and verify streaming behavior behind the actual CDN or proxy. In a Next.js application, use the App Router and run a production build before release.",
        ].join("\n"),
        spokenText: "React Server Components keep data work on the server and hydrate only interactive client boundaries. Test the boundary rules and production streaming before deployment.",
      }
    : undefined;
  const localized = /मलाई|बुझाऊ|कसरी/.test(text)
    ? {
        language: "ne-NP" as const,
        displayText: "ComfyUI को setup गर्न पहिले Python environment, compatible NVIDIA driver र CUDA जाँच्नुहोस्। त्यसपछि ComfyUI install गरेर Stable Diffusion checkpoint लाई `models/checkpoints` मा राख्नुहोस्। Browser मा `http://127.0.0.1:8188` खोल्नुहोस् र workflow queue गर्नुहोस्। Note: HINAA मा real generation local ComfyUI service चलिरहेको बेला मात्र हुन्छ।",
        spokenText: "Python, NVIDIA driver र CUDA तयार भएपछि checkpoint राखेर 8188 मा ComfyUI चलाउनुहोस्।",
      }
    : /मुझे|समझाओ|कैसे/.test(text)
      ? {
          language: "hi-IN" as const,
          displayText: "ComfyUI सेटअप के लिए पहले Python environment, compatible NVIDIA driver और CUDA जाँचें। फिर ComfyUI install करके Stable Diffusion checkpoint को `models/checkpoints` में रखें। Browser में `http://127.0.0.1:8188` खोलें और workflow queue करें। Note: HINAA में real generation तभी चलेगी जब local ComfyUI service चल रही हो।",
          spokenText: "Python, NVIDIA driver और CUDA तैयार करें; checkpoint रखकर 8188 पर ComfyUI service शुरू करें।",
        }
      : undefined;
  const selected = responses.find((response) => response.match.test(text));
  const fallback = [
    "Main abhi mock mode mein hoon. Yeh ek demo response hai — real AI response nahi hai. Real brain ke liye Settings mein jaake Gemini ya OpenAI select karo.",
    "HINAA mock mode: Main aapke sawaal ko samajh rahi hoon, lekin real answer dene ke liye mujhe ek real AI brain ki zaroorat hai. Settings > Provider mein jaake select karo.",
    "Demo mode active hai. Real conversations, web search, image generation aur tools use karne ke liye kripya real provider mode enable karein.",
  ][stableIndex(text) % 3];
  const displayText = professional?.displayText ?? localized?.displayText ?? selected?.text ?? fallback;
  const spokenText = professional?.spokenText ?? localized?.spokenText ?? displayText;
  const primary =
    selected?.emotion ?? (companionId === "hinaa" ? "playful" : "happy");
  const gesture =
    selected?.gesture ??
    (companionId === "hinaa" ? "gentle_head_tilt" : "small_nod");

  return parseAssistantTurnPlan({
    spokenText,
    displayText,
    language: professional?.language ?? localized?.language ?? "mixed",
    emotion: {
      primary,
      intensity: primary === "concerned" ? 0.48 : 0.62,
      valence: primary === "concerned" ? 0.05 : 0.55,
      arousal: primary === "thinking" ? 0.15 : 0.32,
    },
    performance: {
      facePreset:
        primary === "concerned"
          ? "concerned"
          : primary === "thinking"
            ? "thinking"
            : "soft_smile",
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
    this.delayMs = options.delayMs ?? 260;
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
    const plan = buildMockPlan(request.text, request.companionId);
    const chunks = plan.displayText.split(/(?<=\s)/);
    for (const delta of chunks) {
      await abortableDelay(Math.max(12, this.delayMs / 12), request.signal);
      yield { type: "text.delta", delta };
    }
    yield { type: "plan", plan };
  }
}
