import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAudioPlayback } from "./useAudioPlayback";

class FakeUtterance {
  lang = "";
  rate = 1;
  pitch = 1;
  volume = 1;
  voice: SpeechSynthesisVoice | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly text: string) {}
}

describe("useAudioPlayback browser fallback", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("speaks a completed reply through the device voice and retains lip-sync playback state", async () => {
    const speak = vi.fn();
    const cancel = vi.fn();
    vi.stubGlobal("speechSynthesis", {
      getVoices: () => [],
      speak,
      cancel,
    });
    vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
    vi.stubGlobal("AudioContext", undefined);

    const { result } = renderHook(() => useAudioPlayback());
    await act(async () => {
      await expect(result.current.speakBrowser("Hello Unesh, I am here.", "en-US")).resolves.toBe(true);
    });

    expect(speak).toHaveBeenCalledTimes(1);
    const utterance = speak.mock.calls[0][0] as FakeUtterance;
    expect(utterance.text).toBe("Hello Unesh, I am here.");
    expect(utterance.lang).toBe("en-US");
    expect(result.current.playing).toBe(true);
    expect(result.current.visemeEvents.current.length).toBeGreaterThan(0);

    await act(async () => utterance.onend?.());
    expect(result.current.playing).toBe(false);
  });
});
