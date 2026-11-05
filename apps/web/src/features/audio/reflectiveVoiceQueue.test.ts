import { describe, expect, it, vi } from "vitest";
import { ProgressiveSpeech, type SpeechAudio } from "./progressiveSpeech";

const mockAudio: SpeechAudio = { blob: new Blob(["audio"]), provider: "test", latencyMs: 1 };
const tick = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

describe("Reflective Voice & Progressive Speech Coordinator", () => {
  it("enforces idempotency and prevents duplicate phrases from playing", async () => {
    const played: string[] = [];
    const queue = new ProgressiveSpeech({
      synthesize: vi.fn().mockResolvedValue(mockAudio),
      play: async (text) => { played.push(text); },
    });

    // Enqueue phrase with unique key
    const first = queue.enqueue("First point about architecture.", "idem-key-001");
    expect(first).toBe(true);

    // Duplicate enqueue with exact same key must be dropped
    const duplicate = queue.enqueue("First point about architecture.", "idem-key-001");
    expect(duplicate).toBe(false);

    await tick();
    expect(played).toEqual(["First point about architecture."]);
  });

  it("drops stale segments when generation ID advances", async () => {
    const played: string[] = [];
    const queue = new ProgressiveSpeech({
      synthesize: vi.fn().mockResolvedValue(mockAudio),
      play: async (text) => { played.push(text); },
      generationId: 2,
    });

    // Stale generation 1 chunk
    const stale = queue.enqueue("Stale previous generation audio.", "key-stale", 1);
    expect(stale).toBe(false);

    // Current generation 2 chunk
    const current = queue.enqueue("Fresh generation audio.", "key-fresh", 2);
    expect(current).toBe(true);

    await tick();
    expect(played).toEqual(["Fresh generation audio."]);
  });
});
