export interface VadDecision {
  speechStart: boolean;
  speechCommit: boolean;
  bargeIn: boolean;
}

export interface VadOptions {
  startThreshold: number;
  speakerThreshold: number;
  startFrames: number;
  minimumSpeechFrames: number;
  silenceFrames: number;
}

const defaults: VadOptions = {
  startThreshold: 0.025,
  speakerThreshold: 0.07,
  startFrames: 3,
  minimumSpeechFrames: 5,
  silenceFrames: 35,
};

export class LocalVad {
  private hotFrames = 0;
  private voicedFrames = 0;
  private quietFrames = 0;
  private speaking = false;
  private readonly options: VadOptions;

  constructor(options: VadOptions = defaults) {
    this.options = options;
  }

  process(level: number, assistantPlaying: boolean): VadDecision {
    const threshold = assistantPlaying
      ? this.options.speakerThreshold
      : this.options.startThreshold;
    const hot = level >= threshold;
    this.hotFrames = hot ? this.hotFrames + 1 : 0;
    const bargeIn =
      assistantPlaying && this.hotFrames === this.options.startFrames;
    let speechStart = false;
    let speechCommit = false;
    if (!this.speaking && this.hotFrames >= this.options.startFrames) {
      this.speaking = true;
      this.voicedFrames = this.hotFrames;
      this.quietFrames = 0;
      speechStart = true;
    } else if (this.speaking) {
      if (hot) {
        this.voicedFrames += 1;
        this.quietFrames = 0;
      } else {
        this.quietFrames += 1;
      }
      if (
        this.voicedFrames >= this.options.minimumSpeechFrames &&
        this.quietFrames >= this.options.silenceFrames
      ) {
        speechCommit = true;
        this.reset();
      }
    }
    return { speechStart, speechCommit, bargeIn };
  }

  reset() {
    this.hotFrames = 0;
    this.voicedFrames = 0;
    this.quietFrames = 0;
    this.speaking = false;
  }
}
