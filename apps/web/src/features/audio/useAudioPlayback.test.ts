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
  onstart: (() => void) | null = null;

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
      await expect(result.current.speakBrowser("Hello babe, I am here.", "en-US")).resolves.toBe(true);
    });

    expect(speak).toHaveBeenCalledTimes(1);
    const utterance = speak.mock.calls[0][0] as FakeUtterance;
    expect(utterance.text).toBe("Hello babe, I am here.");
    expect(utterance.lang).toBe("en-US");
    expect(result.current.playing).toBe(false);
    expect(result.current.speech.current.state).toBe("queued");
    await act(async () => utterance.onstart?.());
    expect(result.current.playing).toBe(true);
    expect(result.current.visemeEvents.current.length).toBeGreaterThan(0);

    await act(async () => utterance.onend?.());
    expect(result.current.playing).toBe(false);
    expect(result.current.speech.current.state).toBe("idle");
    expect(result.current.visemeEvents.current).toEqual([]);
  });
  it("installs a fresh playback clock for each streamed browser phrase", async () => {
    const speak = vi.fn();
    vi.stubGlobal("speechSynthesis", { getVoices: () => [], speak, cancel: vi.fn() });
    vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
    vi.stubGlobal("AudioContext", undefined);
    const { result } = renderHook(() => useAudioPlayback());
    const ended = vi.fn();
    await act(async () => { await result.current.speakStreamChunk("First phrase.", true, "en-US", "hinaa", ended); });
    const first = speak.mock.calls[0][0] as FakeUtterance;
    await act(async () => first.onstart?.());
    expect(result.current.speech.current.source).toBe("browser");
    expect(result.current.speech.current.timing?.isPlaying()).toBe(true);
    await act(async () => first.onend?.());
    expect(ended).toHaveBeenCalledTimes(1);
    await act(async () => { await result.current.speakStreamChunk("Different second phrase.", false, "en-US", "hinaa"); });
    await act(async () => (speak.mock.calls[1][0] as FakeUtterance).onstart?.());
    expect(result.current.speech.current.events[0].timeMs).toBe(0);
    expect(result.current.speech.current.timing?.isPlaying()).toBe(true);
    act(() => result.current.stop());
  });

  it("replays every streamed phrase, rather than only the last one", async () => {
    const speak=vi.fn();
    vi.stubGlobal("speechSynthesis", {getVoices:()=>[],speak,cancel:vi.fn()});
    vi.stubGlobal("SpeechSynthesisUtterance", FakeUtterance);
    vi.stubGlobal("AudioContext", undefined);
    const { result }=renderHook(()=>useAudioPlayback());
    act(()=>result.current.beginSpeechStream());
    await act(async()=> { await result.current.speakStreamChunk("First phrase.",true,"en-US","hinaa"); });
    await act(async()=> (speak.mock.calls[0][0] as FakeUtterance).onend?.());
    await act(async()=> { await result.current.speakStreamChunk("Second phrase.",false,"en-US","hinaa"); });
    await act(async()=> (speak.mock.calls[1][0] as FakeUtterance).onend?.());
    let replay!: Promise<void>;
    act(()=>{ replay=result.current.replay(); });
    expect(speak.mock.calls[2][0].text).toBe("First phrase.");
    await act(async()=> (speak.mock.calls[2][0] as FakeUtterance).onend?.());
    expect(speak.mock.calls[3][0].text).toBe("Second phrase.");
    await act(async()=> { (speak.mock.calls[3][0] as FakeUtterance).onend?.(); await replay; });
  });

});


describe("cloud voice playback failures", () => {
  afterEach(() => vi.unstubAllGlobals());
  function graph(state: string) {
    return {
      state, destination: {}, resume: vi.fn(async () => {}), close: vi.fn(async () => {}),
      createGain: () => ({ gain: { value: 1 }, connect: vi.fn() }),
      createAnalyser: () => ({ connect: vi.fn() }),
      decodeAudioData: vi.fn(async () => { throw new Error("Invalid MP3"); }),
      createBuffer: vi.fn(),
    };
  }
  it("reports an audio context that remains blocked after resume", async () => {
    const context = graph("suspended");
    vi.stubGlobal("AudioContext", class { constructor() { return context; } });
    const { result } = renderHook(() => useAudioPlayback());
    const ended = vi.fn();
    await act(async () => {
      await expect(result.current.play(new Blob([], { type: "audio/mpeg" }), "Hello", undefined, ended)).rejects.toThrow("Audio is blocked");
    });
    expect(context.resume).toHaveBeenCalled();
    expect(ended).toHaveBeenCalledTimes(1);
    expect(result.current.playing).toBe(false);
  });
  it("does not reinterpret invalid MP3 bytes as noisy raw samples", async () => {
    const context = graph("running");
    vi.stubGlobal("AudioContext", class { constructor() { return context; } });
    const { result } = renderHook(() => useAudioPlayback());
    const blob = new Blob([], { type: "audio/mpeg" });
    Object.defineProperty(blob, "arrayBuffer", { value: async () => new Uint8Array([1, 2, 3, 4]).buffer });
    await act(async () => {
      await expect(result.current.play(blob, "Hello")).rejects.toThrow("could not be decoded");
    });
    expect(context.createBuffer).not.toHaveBeenCalled();
    expect(result.current.playing).toBe(false);
  });
});
