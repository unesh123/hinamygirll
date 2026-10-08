export const TARGET_SAMPLE_RATE = 16_000;

export function resampleMono(
  source: Float32Array,
  sourceRate: number,
  targetRate = TARGET_SAMPLE_RATE,
): Float32Array {
  if (sourceRate === targetRate) return source.slice();
  const length = Math.max(
    1,
    Math.round(source.length * (targetRate / sourceRate)),
  );
  const output = new Float32Array(length);
  const ratio = sourceRate / targetRate;
  for (let index = 0; index < length; index += 1) {
    const position = index * ratio;
    const left = Math.floor(position);
    const right = Math.min(source.length - 1, left + 1);
    const mix = position - left;
    output[index] = source[left] * (1 - mix) + source[right] * mix;
  }
  return output;
}

export function encodePcmWav(samples: Float32Array): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const write = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1)
      view.setUint8(offset + index, value.charCodeAt(index));
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, TARGET_SAMPLE_RATE, true);
  view.setUint32(28, TARGET_SAMPLE_RATE * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(
      44 + index * 2,
      sample < 0 ? sample * 0x8000 : sample * 0x7fff,
      true,
    );
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export function pcm16ToWavBlob(
  pcmBytes: Uint8Array,
  sampleRate = 24_000,
  channels = 1,
): Blob {
  const buffer = new ArrayBuffer(44 + pcmBytes.byteLength);
  const view = new DataView(buffer);
  const write = (offset: number, value: string) => {
    for (let index = 0; index < value.length; index += 1)
      view.setUint8(offset + index, value.charCodeAt(index));
  };
  const byteRate = sampleRate * channels * 2;
  const blockAlign = channels * 2;

  write(0, "RIFF");
  view.setUint32(4, 36 + pcmBytes.byteLength, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, channels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true); // 16-bit
  write(36, "data");
  view.setUint32(40, pcmBytes.byteLength, true);

  new Uint8Array(buffer, 44).set(pcmBytes);
  return new Blob([buffer], { type: "audio/wav" });
}
