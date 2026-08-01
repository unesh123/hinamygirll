class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pending = [];
    this.phase = 0;
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    const ratio = sampleRate / 16000;
    while (this.phase < input.length) {
      const left = Math.floor(this.phase);
      const right = Math.min(input.length - 1, left + 1);
      const mix = this.phase - left;
      this.pending.push(input[left] * (1 - mix) + input[right] * mix);
      this.phase += ratio;
    }
    this.phase -= input.length;
    while (this.pending.length >= 320) {
      const frame = this.pending.splice(0, 320);
      const pcm = new Int16Array(320);
      let energy = 0;
      for (let index = 0; index < frame.length; index += 1) {
        const sample = Math.max(-1, Math.min(1, frame[index]));
        energy += sample * sample;
        pcm[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
      }
      this.port.postMessage(
        { frame: pcm.buffer, level: Math.sqrt(energy / frame.length) },
        [pcm.buffer],
      );
    }
    return true;
  }
}

registerProcessor("hinaa-pcm-capture", PcmCaptureProcessor);
