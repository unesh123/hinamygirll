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
  const displayText = localized?.displayText ?? selected?.text ?? fallback;
  const spokenText = localized?.spokenText ?? displayText;
  const primary =
    selected?.emotion ?? (companionId === "hinaa" ? "playful" : "happy");
  const gesture =
    selected?.gesture ??
    (companionId === "hinaa" ? "gentle_head_tilt" : "small_nod");

  return parseAssistantTurnPlan({
    spokenText,
    displayText,
    language: localized?.language ?? "mixed",
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
