import { describe, expect, it, vi } from "vitest";
import { withSpeechFallback } from "./speechFallback";

describe("speech synthesis fallback", () => {
  it("recovers from unavailable timing with the same deadline signal", async () => {
    let firstSignal: AbortSignal | undefined;
    const fallback = vi.fn(async (signal: AbortSignal) => {
      expect(signal).toBe(firstSignal);
      return "audio";
    });
    const result = await withSpeechFallback(new AbortController().signal, async signal => {
      firstSignal = signal;
      throw new Error("alignment unavailable");
    }, fallback);
    expect(result).toBe("audio");
    expect(fallback).toHaveBeenCalledOnce();
  });

  it("does not launch another request after cancellation", async () => {
    const controller = new AbortController();
    const fallback = vi.fn(async () => "audio");
    await expect(withSpeechFallback(controller.signal, async () => {
      controller.abort();
      throw new Error("aborted request");
    }, fallback)).rejects.toMatchObject({ name: "AbortError" });
    expect(fallback).not.toHaveBeenCalled();
  });

  it("does not retry after the shared timeout expires", async () => {
    const fallback = vi.fn(async () => "audio");
    const pending = withSpeechFallback(new AbortController().signal, signal => new Promise<string>((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    }), fallback, 5);
    await expect(pending).rejects.toMatchObject({ name: "TimeoutError" });
    expect(fallback).not.toHaveBeenCalled();
  });

  it("never starts synthesis for an already cancelled turn", async () => {
    const controller = new AbortController();
    controller.abort();
    const timed = vi.fn(async () => "audio");
    await expect(withSpeechFallback(controller.signal, timed, timed)).rejects.toMatchObject({ name: "AbortError" });
    expect(timed).not.toHaveBeenCalled();
  });
});
