export type ToolActivityOutcome = {
  status: "complete" | "blocked" | "error";
  label: string;
  result: unknown;
};

type ToolEnvelope = {
  status?: unknown;
  data?: unknown;
  detail?: unknown;
  error?: unknown;
};

type PlaybackEvidence = {
  verified?: unknown;
  state?: unknown;
  message?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function safeText(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback;
  const cleaned = value.replace(/\s+/g, " ").trim();
  return cleaned ? cleaned.slice(0, 220) : fallback;
}

/**
 * A remote tool can finish its HTTP call without completing the user’s goal.
 * Keep that distinction visible, especially for browser media playback.
 */
export function resolveToolOutcome(toolName: string, payload: unknown): ToolActivityOutcome {
  const envelope: ToolEnvelope = isRecord(payload) ? payload : {};
  const result = envelope.data ?? payload;
  const evidence: PlaybackEvidence = isRecord(result) ? result : {};
  const message = safeText(evidence.message ?? envelope.detail ?? envelope.error, "The action needs your attention.");

  if (envelope.status === "error") {
    return { status: "error", label: `Failed: ${message}`, result };
  }

  const blocked = envelope.status === "blocked" || evidence.verified === false;
  if (blocked) {
    const playbackBlocked = toolName === "youtube_playback_request";
    return {
      status: "blocked",
      label: playbackBlocked ? `YouTube needs you: ${message}` : `Needs attention: ${message}`,
      result,
    };
  }

  if (toolName === "youtube_playback_request" && evidence.verified !== true) {
    return {
      status: "blocked",
      label: "YouTube needs you: playback was not verified in HINAA's owned tab.",
      result,
    };
  }

  if (toolName === "youtube_playback_request") {
    return {
      status: "complete",
      label: `Playing verified: ${message}`,
      result,
    };
  }

  return { status: "complete", label: `Completed: ${toolName}`, result };
}
