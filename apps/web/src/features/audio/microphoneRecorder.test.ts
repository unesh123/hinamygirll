import { afterEach, describe, expect, it, vi } from "vitest";
import { MicrophoneRecorder } from "./microphoneRecorder";

afterEach(() => vi.unstubAllGlobals());

describe("MicrophoneRecorder", () => {
  it("stops every track and closes audio nodes after capture", async () => {
    const stopTrack = vi.fn();
    const disconnectSource = vi.fn();
    const disconnectProcessor = vi.fn();
    const disconnectSink = vi.fn();
    const close = vi.fn(async () => undefined);
    let process: ScriptProcessorNode["onaudioprocess"] = null;

    const processor = {
      connect: vi.fn(),
      disconnect: disconnectProcessor,
      get onaudioprocess() {
        return process;
      },
      set onaudioprocess(value) {
        process = value;
      },
    } as unknown as ScriptProcessorNode;
    const context = {
      sampleRate: 48_000,
      state: "running",
      destination: {},
      resume: vi.fn(async () => undefined),
      close,
      createMediaStreamSource: vi.fn(() => ({
        connect: vi.fn(),
        disconnect: disconnectSource,
      })),
      createScriptProcessor: vi.fn(() => processor),
      createGain: vi.fn(() => ({
        gain: { value: 1 },
        connect: vi.fn(),
        disconnect: disconnectSink,
      })),
    } as unknown as AudioContext;

    function FakeAudioContext() {
      return context;
    }
    vi.stubGlobal(
      "AudioContext",
      FakeAudioContext as unknown as typeof AudioContext,
    );
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi.fn(async () => ({
          getTracks: () => [{ stop: stopTrack }],
        })),
      },
    });

    const recorder = new MicrophoneRecorder();
    await recorder.start();
    const handler = processor.onaudioprocess;
    if (!handler)
      throw new Error("Recorder did not attach its process handler");
    handler.call(processor, {
      inputBuffer: {
        getChannelData: () => Float32Array.from([0.1, -0.1, 0.2]),
      },
    } as unknown as AudioProcessingEvent);
    const wav = await recorder.stop();

    expect(wav.type).toBe("audio/wav");
    expect(stopTrack).toHaveBeenCalledOnce();
    expect(disconnectSource).toHaveBeenCalledOnce();
    expect(disconnectProcessor).toHaveBeenCalledOnce();
    expect(disconnectSink).toHaveBeenCalledOnce();
    expect(close).toHaveBeenCalledOnce();
  });
});
