import { describe, expect, it } from "vitest";
import { encodePcmWav, resampleMono } from "./pcm";

describe("browser PCM conversion", () => {
  it("resamples mono audio and emits the required WAV header", async () => {
    const source = Float32Array.from({ length: 48_000 }, (_, index) =>
      Math.sin((index / 48_000) * Math.PI * 2 * 220),
    );
    const resampled = resampleMono(source, 48_000);
    expect(resampled).toHaveLength(16_000);
    const wav = encodePcmWav(resampled);
    expect(wav.type).toBe("audio/wav");
    expect(new TextDecoder().decode(await wav.slice(0, 4).arrayBuffer())).toBe(
      "RIFF",
    );
    const header = new DataView(await wav.slice(0, 44).arrayBuffer());
    expect(header.getUint32(24, true)).toBe(16_000);
    expect(header.getUint16(22, true)).toBe(1);
    expect(header.getUint16(34, true)).toBe(16);
  });

  it("clamps samples before encoding", async () => {
    const wav = encodePcmWav(Float32Array.from([-2, 2]));
    const data = new DataView(await wav.arrayBuffer());
    expect(data.getInt16(44, true)).toBe(-32768);
    expect(data.getInt16(46, true)).toBe(32767);
  });
});
