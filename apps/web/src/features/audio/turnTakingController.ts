export type TurnTakingState =
  | "inactive"
  | "initializing"
  | "listening"
  | "possible_speech"
  | "active_speech"
  | "hesitation"
  | "possible_end_of_turn"
  | "committing"
  | "waiting_for_provider"
  | "speaking"
  | "interrupted"
  | "reconnecting"
  | "provider_unavailable"
  | "microphone_denied"
  | "error";

export interface TurnTakingConfig {
  /** Frames above threshold before speech start (~20ms each). */
  startFrames: number;
  /** Minimum voiced frames before a commit is allowed. */
  minimumSpeechFrames: number;
  /** Short silence treated as hesitation, not end-of-turn. */
  hesitationFrames: number;
  /** Silence frames required to end a turn when partial looks complete. */
  endOfTurnFrames: number;
  /** Hard silence ceiling before forced commit. */
  maxSilenceFrames: number;
  /** Hard max speech frames (~20ms) before force commit. */
  maxSpeechFrames: number;
  startThreshold: number;
  speakerThreshold: number;
  /** Reject commits shorter than this many characters of last partial. */
  minimumTranscriptChars: number;
}

export const DEFAULT_TURN_TAKING: TurnTakingConfig = {
  startFrames: 3,
  minimumSpeechFrames: 5,
  hesitationFrames: 12,
  endOfTurnFrames: 28,
  maxSilenceFrames: 45,
  maxSpeechFrames: 1_500,
  startThreshold: 0.025,
  speakerThreshold: 0.07,
  minimumTranscriptChars: 2,
};

export interface TurnTakingInput {
  level: number;
  assistantPlaying: boolean;
  partialText: string;
  sessionActive: boolean;
  paused: boolean;
}

export interface TurnTakingDecision {
  state: TurnTakingState;
  speechStart: boolean;
  speechCommit: boolean;
  bargeIn: boolean;
  reason?: string;
}

const INCOMPLETE_TAIL =
  /\b(and|or|but|because|so|to|the|a|an|ko|ra|ani|tara|ki|ki|aur|ya|ke|ka|se|me|mein)\s*$/i;

function looksComplete(partial: string): boolean {
  const text = partial.trim();
  if (text.length < 2) return false;
  if (/[.!?।…]$/.test(text)) return true;
  if (INCOMPLETE_TAIL.test(text)) return false;
  return text.split(/\s+/).length >= 3;
}

/**
 * Deterministic multi-signal turn-taking controller for hands-free live mode.
 * Does not diagnose emotion or speaker identity.
 */
export class TurnTakingController {
  private state: TurnTakingState = "inactive";
  private hotFrames = 0;
  private voicedFrames = 0;
  private quietFrames = 0;
  private speaking = false;
  private lastPartial = "";
  private lastCommitFingerprint = "";
  private readonly config: TurnTakingConfig;

  constructor(config: Partial<TurnTakingConfig> = {}) {
    this.config = { ...DEFAULT_TURN_TAKING, ...config };
  }

  get currentState(): TurnTakingState {
    return this.state;
  }

  setSessionState(next: TurnTakingState): void {
    this.state = next;
  }

  notePartial(text: string): void {
    this.lastPartial = text.trim();
  }

  resetSpeech(): void {
    this.hotFrames = 0;
    this.voicedFrames = 0;
    this.quietFrames = 0;
    this.speaking = false;
  }

  process(input: TurnTakingInput): TurnTakingDecision {
    if (!input.sessionActive) {
      this.resetSpeech();
      this.state = "inactive";
      return {
        state: this.state,
        speechStart: false,
        speechCommit: false,
        bargeIn: false,
      };
    }
    if (input.paused) {
      this.resetSpeech();
      this.state = "listening";
      return {
        state: this.state,
        speechStart: false,
        speechCommit: false,
        bargeIn: false,
        reason: "paused",
      };
    }

    const threshold = input.assistantPlaying
      ? this.config.speakerThreshold
      : this.config.startThreshold;
    const hot = input.level >= threshold;
    this.hotFrames = hot ? this.hotFrames + 1 : 0;
    const bargeIn =
      input.assistantPlaying && this.hotFrames === this.config.startFrames;

    if (input.partialText.trim()) this.lastPartial = input.partialText.trim();

    let speechStart = false;
    let speechCommit = false;
    let reason: string | undefined;

    if (!this.speaking && this.hotFrames >= this.config.startFrames) {
      this.speaking = true;
      this.voicedFrames = this.hotFrames;
      this.quietFrames = 0;
      speechStart = true;
      this.state = "active_speech";
      reason = "energy_start";
    } else if (this.speaking) {
      if (hot) {
        this.voicedFrames += 1;
        this.quietFrames = 0;
        this.state = "active_speech";
      } else {
        this.quietFrames += 1;
        if (this.quietFrames <= this.config.hesitationFrames) {
          this.state = "hesitation";
        } else {
          this.state = "possible_end_of_turn";
        }
      }

      const enoughSpeech = this.voicedFrames >= this.config.minimumSpeechFrames;
      const hasTranscript =
        this.lastPartial.length >= this.config.minimumTranscriptChars;
      const complete = looksComplete(this.lastPartial);
      const softEnd =
        enoughSpeech &&
        hasTranscript &&
        this.quietFrames >= this.config.endOfTurnFrames &&
        (complete || hasTranscript);
      const hardSilence =
        enoughSpeech &&
        hasTranscript &&
        this.quietFrames >= this.config.maxSilenceFrames;
      const hardMax =
        hasTranscript && this.voicedFrames >= this.config.maxSpeechFrames;

      if ((softEnd || hardSilence || hardMax) && hasTranscript) {
        const fingerprint = `${this.lastPartial}|${this.voicedFrames}`;
        if (fingerprint === this.lastCommitFingerprint) {
          this.resetSpeech();
          this.state = "listening";
          return {
            state: this.state,
            speechStart: false,
            speechCommit: false,
            bargeIn,
            reason: "duplicate_commit_suppressed",
          };
        }
        this.lastCommitFingerprint = fingerprint;
        speechCommit = true;
        reason = hardMax
          ? "max_speech"
          : hardSilence
            ? "max_silence"
            : "end_of_turn";
        this.resetSpeech();
        this.state = "committing";
      } else if (
        enoughSpeech &&
        (this.quietFrames >= this.config.maxSilenceFrames || hardMax) &&
        !hasTranscript
      ) {
        this.resetSpeech();
        this.state = "listening";
        reason = "empty_or_noise_rejected";
      }
    } else if (this.hotFrames > 0) {
      this.state = "possible_speech";
    } else if (input.assistantPlaying) {
      this.state = "speaking";
    } else {
      this.state = "listening";
    }

    if (bargeIn) {
      this.resetSpeech();
      this.state = "interrupted";
      reason = reason ?? "barge_in";
    }

    return {
      state: this.state,
      speechStart,
      speechCommit,
      bargeIn,
      reason,
    };
  }
}
