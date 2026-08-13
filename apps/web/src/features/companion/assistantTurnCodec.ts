import {
  assistantTurnPlanSchema,
  type AssistantTurnPlan,
} from "../../contracts/assistantTurnPlan";

const TURN_PREFIX = "hinaa.assistant-turn/v1:";

type SerializedAssistantTurn = {
  version: 1;
  turn: AssistantTurnPlan;
};

function decodeStructuredPayload(value: unknown): AssistantTurnPlan | undefined {
  if (!value || typeof value !== "object") return undefined;
  const candidate = value as Partial<SerializedAssistantTurn>;
  const parsed = assistantTurnPlanSchema.safeParse(candidate.turn ?? value);
  return parsed.success ? parsed.data : undefined;
}

function parseStructuredJsonText(value: string): AssistantTurnPlan | undefined {
  const trimmed = value.trim();
  const fenced = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i)?.[1]?.trim() ?? trimmed;
  if (!fenced.startsWith("{")) return undefined;
  try {
    return decodeStructuredPayload(JSON.parse(fenced));
  } catch {
    return undefined;
  }
}

/** Persist a structured assistant response without exposing raw payloads to UI/TTS. */
export function serializeAssistantTurn(turn: AssistantTurnPlan): string {
  return `${TURN_PREFIX}${JSON.stringify({ version: 1, turn } satisfies SerializedAssistantTurn)}`;
}

/**
 * Decode the current persisted format and prior raw plan objects. Legacy plain
 * text remains valid conversation history and deliberately returns undefined.
 */
export function deserializeAssistantTurn(content: unknown): AssistantTurnPlan | undefined {
  if (typeof content !== "string") return decodeStructuredPayload(content);
  const encoded = content.startsWith(TURN_PREFIX) ? content.slice(TURN_PREFIX.length) : content;
  return parseStructuredJsonText(encoded);
}

export function getAssistantDisplayText(content: unknown): string {
  const turn = deserializeAssistantTurn(content);
  if (turn) return turn.displayText;
  if (typeof content === "string" && content.startsWith(TURN_PREFIX)) {
    return "A saved response could not be restored safely.";
  }
  return typeof content === "string" ? content : "";
}

export function getAssistantSpokenText(content: unknown): string {
  const turn = deserializeAssistantTurn(content);
  return turn?.spokenText ?? getAssistantDisplayText(content);
}

export function getAssistantArtifacts(content: unknown): AssistantTurnPlan["toolRequests"] {
  return deserializeAssistantTurn(content)?.toolRequests ?? [];
}
