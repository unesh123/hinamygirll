import { describe, expect, it, vi } from "vitest";
import { ProgressiveSpeech, type SpeechAudio } from "./progressiveSpeech";
const audio: SpeechAudio = { blob: new Blob(["audio"]), provider: "test", latencyMs: 1 };
const tick = async () => { for (let i=0;i<8;i++) await Promise.resolve(); };

describe("progressive voice queue", () => {
  it("starts the first phrase without waiting for the answer and prefetches in order", async () => {
    const resolve = new Map<string, (audio: SpeechAudio) => void>();
    const finish: Array<() => void> = [];
    const played: string[] = [];
    const synthesize = vi.fn((text: string) => new Promise<SpeechAudio>(done => resolve.set(text, done)));
    const queue = new ProgressiveSpeech({ synthesize, play: async text => { played.push(text); await new Promise<void>(done => finish.push(done)); } });
    queue.enqueue("First."); queue.enqueue("Second."); queue.enqueue("Third."); queue.enqueue("Fourth.");
    expect(synthesize).toHaveBeenCalledTimes(3);
    resolve.get("Second.")!(audio); await tick();
    expect(played).toEqual([]);
    resolve.get("First.")!(audio); await tick();
    expect(played).toEqual(["First."]);
    finish[0](); await tick();
    expect(played).toEqual(["First.", "Second."]);
    queue.cancel();
  });
  it("cancels pending synthesis and never starts stale audio", async () => {
    let complete!: (audio: SpeechAudio) => void;
    let signal!: AbortSignal;
    const play = vi.fn();
    const queue = new ProgressiveSpeech({ synthesize: (_text, turnSignal) => { signal = turnSignal; return new Promise(done => { complete=done; }); }, play });
    queue.enqueue("Old reply."); queue.cancel(); complete(audio); await tick();
    expect(signal.aborted).toBe(true); expect(play).not.toHaveBeenCalled();
  });
  it("falls back once per remaining phrase without replaying preceding text", async () => {
    const played: string[] = [];
    const queue = new ProgressiveSpeech({ synthesize: vi.fn().mockRejectedValue(new Error("Unavailable")), play: async (text, result) => { expect(result).toBeNull(); played.push(text); } });
    queue.enqueue("First."); queue.enqueue("Second."); await tick();
    expect(played).toEqual(["First.", "Second."]);
  });
});
