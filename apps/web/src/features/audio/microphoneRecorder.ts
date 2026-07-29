import { encodePcmWav, resampleMono } from "./pcm";

export class MicrophoneRecorder {
  private stream?: MediaStream;
  private context?: AudioContext;
  private source?: MediaStreamAudioSourceNode;
  private processor?: ScriptProcessorNode;
  private sink?: GainNode;
  private chunks: Float32Array[] = [];
  private sampleRate = 48_000;

  async start(): Promise<void> {
    if (!navigator.mediaDevices?.getUserMedia)
      throw new DOMException(
        "Microphone capture is unsupported",
        "NotSupportedError",
      );
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: false,
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const AudioContextClass = globalThis.AudioContext;
    this.context = new AudioContextClass({ latencyHint: "interactive" });
    await this.context.resume();
    this.sampleRate = this.context.sampleRate;
    this.source = this.context.createMediaStreamSource(this.stream);
    this.processor = this.context.createScriptProcessor(4096, 1, 1);
    this.sink = this.context.createGain();
    this.sink.gain.value = 0;
    this.processor.onaudioprocess = (event) => {
      this.chunks.push(event.inputBuffer.getChannelData(0).slice());
    };
    this.source.connect(this.processor);
    this.processor.connect(this.sink);
    this.sink.connect(this.context.destination);
  }

  async stop(): Promise<Blob> {
    const length = this.chunks.reduce(
      (total, chunk) => total + chunk.length,
      0,
    );
    const samples = new Float32Array(length);
    let offset = 0;
    for (const chunk of this.chunks) {
      samples.set(chunk, offset);
      offset += chunk.length;
    }
    await this.cleanup();
    if (!samples.length) throw new Error("No microphone samples were captured");
    return encodePcmWav(resampleMono(samples, this.sampleRate));
  }

  async cancel(): Promise<void> {
    await this.cleanup();
  }

  private async cleanup(): Promise<void> {
    this.processor?.disconnect();
    this.source?.disconnect();
    this.sink?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    this.processor = undefined;
    this.source = undefined;
    this.sink = undefined;
    this.stream = undefined;
    this.chunks = [];
    if (this.context && this.context.state !== "closed")
      await this.context.close();
    this.context = undefined;
  }
}
