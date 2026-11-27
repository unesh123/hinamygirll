/**
 * AudioWorklet processor capturing microphone audio, downsampling to 16kHz,
 * and posting 30ms (480-sample) signed 16-bit PCM frames to the main thread.
 */

export const TARGET_SAMPLE_RATE = 16000;
export const FRAME_SAMPLES = 480;

export function downsampleFloat32ToInt16(
  input: Float32Array,
  inputSampleRate: number,
  targetSampleRate: number = TARGET_SAMPLE_RATE,
): Int16Array {
  if (inputSampleRate <= targetSampleRate) {
    const out = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const clamped = Math.max(-1, Math.min(1, input[i]));
      out[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    }
    return out;
  }

  const ratio = inputSampleRate / targetSampleRate;
  const newLen = Math.floor(input.length / ratio);
  const result = new Int16Array(newLen);
  for (let i = 0; i < newLen; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    let count = 0;
    for (let j = start; j < end; j++) {
      sum += input[j];
      count++;
    }
    const avg = count > 0 ? sum / count : 0;
    const clamped = Math.max(-1, Math.min(1, avg));
    result[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
  }
  return result;
}

// Register only when executing inside an AudioWorkletGlobalScope.
const WorkletBase = (globalThis as { AudioWorkletProcessor?: new () => { port: MessagePort } })
  .AudioWorkletProcessor;
const registerWorklet = (
  globalThis as { registerProcessor?: (name: string, ctor: unknown) => void }
).registerProcessor;

if (WorkletBase && registerWorklet) {
  class HinaPcmCaptureProcessor extends WorkletBase {
    private buffer: number[] = [];

    process(inputs: Float32Array[][]): boolean {
      const channel = inputs[0]?.[0];
      if (!channel || channel.length === 0) return true;
      const rate = (globalThis as { sampleRate?: number }).sampleRate ?? 48000;
      const pcm = downsampleFloat32ToInt16(channel, rate, TARGET_SAMPLE_RATE);
      for (let i = 0; i < pcm.length; i++) {
        this.buffer.push(pcm[i]);
      }
      while (this.buffer.length >= FRAME_SAMPLES) {
        const chunk = new Int16Array(this.buffer.splice(0, FRAME_SAMPLES));
        this.port.postMessage(chunk.buffer, [chunk.buffer]);
      }
      return true;
    }
  }

  registerWorklet("hina-pcm-capture", HinaPcmCaptureProcessor);
}
