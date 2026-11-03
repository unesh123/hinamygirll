import { hinaaIdentityHeaders } from "../../lib/hinaaIdentity";
import type { ProviderMode } from "./api";
import type { SpeechAudio } from "./progressiveSpeech";
import { timedAlignmentToVisemes } from "./textToViseme";

/** Consume network frames without waiting for the phrase's complete audio file. */
export async function* readSpeechFrames(response: Response, signal: AbortSignal): AsyncGenerator<SpeechAudio> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Voice stream has no body.");
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener("abort", cancel, { once: true });
  const decoder = new TextDecoder();
  let pending = "";
  let completed = false;
  try {
    while (!completed) {
      signal.throwIfAborted();
      const { value, done } = await reader.read();
      signal.throwIfAborted();
      pending += decoder.decode(value, { stream: !done });
      if (pending.length > 2_000_000) throw new Error("Voice frame exceeds the stream limit.");
      let newline: number;
      while ((newline = pending.indexOf("\n")) >= 0) {
        const line = pending.slice(0, newline).trim();
        pending = pending.slice(newline + 1);
        if (!line) continue;
        const event = JSON.parse(line);
        if (event.type === "error") throw new Error("Voice stream failed. Please retry.");
        if (event.type === "done") { completed = true; break; }
        if (event.type !== "audio" || typeof event.audioBase64 !== "string" || event.sampleRate !== 24_000) {
          throw new Error("Invalid voice stream frame.");
        }
        const raw = atob(event.audioBase64);
        if (!raw.length || raw.length % 2) throw new Error("Invalid PCM voice frame.");
        const bytes = Uint8Array.from(raw, char => char.charCodeAt(0));
        const blob = new Blob([bytes], { type: "audio/pcm" });
        const alignment = Array.isArray(event.alignment) ? event.alignment.map((item: {char: string; startMs: number; endMs: number}) => ({
          char: item.char, startMs: item.startMs, durationMs: item.endMs - item.startMs,
        })) : [];
        yield { blob, provider: "elevenlabs", latencyMs: 0, text: typeof event.text === "string" ? event.text : "", visemes: timedAlignmentToVisemes(alignment) };
      }
      if (done && !completed) throw new Error("Voice stream ended before completion.");
    }
  } finally {
    signal.removeEventListener("abort", cancel);
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export async function synthesizeSpeechStream(
  text: string, companionId: "hinaa" | "hiro", mode: ProviderMode,
  signal: AbortSignal, language: string,
): Promise<SpeechAudio> {
  const started = performance.now();
  const response = await fetch("/api/v1/speech/synthesis/stream", {
    method: "POST", signal,
    headers: { "Content-Type": "application/json", ...hinaaIdentityHeaders() },
    body: JSON.stringify({ text, companionId, providerMode: mode, voiceEngine: "elevenlabs", realtime: true, language }),
  });
  if (!response.ok) throw new Error(`Streaming voice unavailable (${response.status}).`);
  const frames = readSpeechFrames(response, signal);
  const first = await frames.next();
  if (first.done) throw new Error("Voice stream produced no audio.");
  return {
    blob: new Blob(), provider: "elevenlabs", latencyMs: Math.round(performance.now() - started),
    stream: (async function* () {
      try { yield first.value; yield* frames; }
      finally { await frames.return(undefined); }
    })(),
  };
}
