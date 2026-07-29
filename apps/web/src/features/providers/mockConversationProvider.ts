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
    match: /assignment|बुझ|explain/i,
    text: "Sure! Assignment ko main idea lai sano steps ma break garau. Pahila question ko goal herau, ani एउटा example बनाऔँ।",
    emotion: "thinking",
    gesture: "explain",
  },
  {
    match: /mood|off|sad|दुख|मन/i,
    text: "Aaja ali heavy feel bhairako jasto cha—ma गलत पनि हुन सक्छु। Ekchin slow down garne कि kura share garne?",
    emotion: "concerned",
    gesture: "reassure",
  },
  {
    match: /hello|hi|namaste|नमस्ते/i,
    text: "Namaste! Mock mode ekdam ready cha. Text, states, animation वा interruption जे test गरे पनि हुन्छ।",
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
  const selected = responses.find((response) => response.match.test(text));
  const fallback = [
    "Yo deterministic mock response ho—real AI वा cloud service connect भएको छैन। हामी UI र avatar behaviour safely test गर्दैछौँ।",
    "Bujheँ! अहिले mock mode le fixed, repeatable answer दिन्छ। Phase 2 अघि कुनै API key चाहिँदैन।",
    "Nice test! HINAA ko state, transcript र motion cue अहिले local mock बाट चलिरहेका छन्।",
  ][stableIndex(text) % 3];
  const displayText = selected?.text ?? fallback;
  const primary =
    selected?.emotion ?? (companionId === "hinaa" ? "playful" : "happy");
  const gesture =
    selected?.gesture ??
    (companionId === "hinaa" ? "gentle_head_tilt" : "small_nod");

  return parseAssistantTurnPlan({
    spokenText: displayText,
    displayText,
    language: "mixed",
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
