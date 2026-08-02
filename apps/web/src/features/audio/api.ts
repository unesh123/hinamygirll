export type ProviderMode =
  | "mock"
  | "local"
  | "groq"
  | "openai"
  | "custom"
  | "real";

export interface ProviderStatus {
  id: string;
  capabilities: string[];
  state: "healthy" | "degraded" | "unavailable" | "disabled";
  userMessage: string;
}

export async function fetchProviderStatuses(
  signal?: AbortSignal,
): Promise<ProviderStatus[]> {
  const response = await fetch("/api/v1/providers", { signal });
  if (!response.ok)
    throw new Error(`Provider status failed (${response.status})`);
  return (await response.json()) as ProviderStatus[];
}

interface TranscriptResult {
  text: string;
  language: string;
  provider: string;
  latencyMs: number;
}

export async function transcribeAudio(
  blob: Blob,
  mode: ProviderMode,
  signal: AbortSignal,
): Promise<TranscriptResult> {
  const form = new FormData();
  form.append("audio", blob, "microphone-turn.wav");
  form.append("language", "ne-NP");
  form.append("provider_mode", mode);
  const response = await fetch("/api/v1/speech/transcriptions", {
    method: "POST",
    body: form,
    signal,
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as {
      message?: string;
    };
    throw new Error(
      error.message ?? `Transcription failed (${response.status})`,
    );
  }
  return (await response.json()) as TranscriptResult;
}

export async function synthesizeSpeech(
  text: string,
  companionId: "hinaa" | "hiro",
  mode: ProviderMode,
  signal: AbortSignal,
): Promise<{ blob: Blob; provider: string; latencyMs: number }> {
  const response = await fetch("/api/v1/speech/synthesis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, companionId, providerMode: mode }),
    signal,
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as {
      message?: string;
    };
    throw new Error(
      error.message ?? `Voice synthesis failed (${response.status})`,
    );
  }
  return {
    blob: await response.blob(),
    provider: response.headers.get("X-HINAA-Provider") ?? mode,
    latencyMs: Number(response.headers.get("X-HINAA-Latency-Ms") ?? 0),
  };
}
