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
  /** Frames required for intentional user barge-in while assistant speaks. */
  bargeInFrames: number;
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
  /** Optional initial noise floor baseline for noisy microphones/rooms. */
  initialNoiseFloor?: number;
}

export const DEFAULT_TURN_TAKING: TurnTakingConfig = {
  startFrames: 4,               // ~80ms sustained voice onset (rejects 1-frame air puffs & clicks)
  bargeInFrames: 12,           // ~240ms of sustained voice; 3 frames let her own speaker echo interrupt and discard her remaining audio
  minimumSpeechFrames: 8,       // ~160ms minimum voiced frames
  hesitationFrames: 14,         // ~280ms pause treated as natural thinking hesitation
  endOfTurnFrames: 28,          // ~560ms natural pause before turn commit (prevents mid-sentence cutoffs)
  maxSilenceFrames: 40,         // ~800ms hard silence ceiling
  maxSpeechFrames: 1_500,
  startThreshold: 0.012,        // Immune to fan/AC rumble (~0.004-0.006 RMS) while sensitive to speech (>=0.020)
  speakerThreshold: 0.045,      // Responsive threshold for natural voice interruption
  minimumTranscriptChars: 1,
};

export interface TurnTakingInput {
  level: number;
  assistantPlaying: boolean;
  partialText: string;
  sessionActive: boolean;
  paused: boolean;
  waitingForProvider?: boolean;
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
  private noiseFloor = 0.005; // Adaptive background noise baseline (e.g. laptop fans)
  private lastThreshold = 0.015;
  private readonly config: TurnTakingConfig;

  constructor(config: Partial<TurnTakingConfig> = {}) {
    this.config = { ...DEFAULT_TURN_TAKING, ...config };
    if (this.config.initialNoiseFloor !== undefined) {
      this.noiseFloor = Math.max(0.002, Math.min(0.080, this.config.initialNoiseFloor));
      this.lastThreshold = Math.max(this.config.startThreshold, this.noiseFloor * 1.35 + 0.008);
    }
  }

  get currentState(): TurnTakingState {
    return this.state;
  }

  get currentNoiseFloor(): number {
    return this.noiseFloor;
  }

  get currentThreshold(): number {
    return this.lastThreshold;
  }

  calibrateFloor(level: number): void {
    if (level > 0 && level <= 0.080) {
      this.noiseFloor = Math.max(0.002, level);
      this.lastThreshold = Math.max(this.config.startThreshold, this.noiseFloor * 1.35 + 0.008);
    }
  }

  forceSpeechStart(): TurnTakingDecision {
    this.speaking = true;
    this.hotFrames = Math.max(10, this.config.startFrames);
    this.voicedFrames = Math.max(10, this.config.minimumSpeechFrames);
    this.quietFrames = 0;
    this.state = "active_speech";
    return {
      state: this.state,
      speechStart: true,
      speechCommit: false,
      bargeIn: false,
      reason: "push_to_talk",
    };
  }

  forceSpeechCommit(): TurnTakingDecision {
    const wasSpeaking = this.speaking;
    this.resetSpeech();
    this.state = "committing";
    return {
      state: this.state,
      speechStart: false,
      speechCommit: wasSpeaking,
      bargeIn: false,
      reason: "push_to_talk_commit",
    };
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
    this.lastPartial = "";
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

    // Adaptive noise floor tracking — tracks baseline background noise up to 0.080
    // so high-gain laptop mics, headsets, and room noise (e.g. 0.03 - 0.06 RMS)
    // don't get permanently stuck in "speech active".
    const candidateStart = Math.max(
      this.config.startThreshold,
      this.noiseFloor * 1.35 + 0.008,
    );
    if (!this.speaking && !input.assistantPlaying && input.level < candidateStart) {
      this.noiseFloor = Math.min(0.080, Math.max(0.002, this.noiseFloor * 0.96 + input.level * 0.04));
    }

    // Dynamic thresholds with hysteresis:
    // - start threshold requires a clear jump above noise floor
    // - continuation threshold while speaking is slightly lower (hysteresis)
    // - barge-in threshold requires intentional voice over assistant playback
    const dynamicStartThreshold = Math.max(
      this.config.startThreshold,
      this.noiseFloor * 2.0 + 0.008,
    );
    const dynamicContinueThreshold = Math.max(
      this.config.startThreshold * 0.8,
      this.noiseFloor * 1.5 + 0.005,
    );
    const dynamicBargeInThreshold = Math.max(
      input.assistantPlaying ? Math.max(0.045, (this.config.speakerThreshold || 0.045) * 1.5) : 0.040,
      this.noiseFloor * 2.2 + 0.015,
    );

    const isBusy =
      input.assistantPlaying ||
      Boolean(input.waitingForProvider) ||
      this.state === "waiting_for_provider";

    const threshold = isBusy
      ? dynamicBargeInThreshold
      : this.speaking
        ? dynamicContinueThreshold
        : dynamicStartThreshold;
    this.lastThreshold = threshold;

    const hot = input.level >= threshold;
    this.hotFrames = hot ? this.hotFrames + 1 : 0;
    const bargeIn =
      isBusy && this.hotFrames === this.config.bargeInFrames;

    if (input.partialText.trim()) this.lastPartial = input.partialText.trim();

    let speechStart = false;
    let speechCommit = false;
    let reason: string | undefined;

    if (!this.speaking && !isBusy && this.hotFrames >= this.config.startFrames) {
      this.speaking = true;
      this.voicedFrames = this.hotFrames;
      this.quietFrames = 0;
      speechStart = true;
      this.state = "active_speech";
      reason = "energy_start";
    } else if (this.speaking) {
      if (hot) {
        this.voicedFrames += 1;
        // Don't let a single frame of background flutter (fan/AC) completely destroy
        // an active silence period: only decrement if consecutive hot frames >= 2
        if (this.hotFrames >= 2) {
          if (this.quietFrames > 0) {
            this.quietFrames = Math.max(0, this.quietFrames - 2);
          } else {
            this.quietFrames = 0;
          }
        }
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
      // Hard max speech limit fires even without transcript to prevent runaway recordings
      const hardMax = this.voicedFrames >= this.config.maxSpeechFrames;

      if ((softEnd || hardSilence || (hardMax && hasTranscript)) && hasTranscript) {
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
        // Without a transcript (e.g. Claude/CX backend batch STT), commit once user has
        // spoken for a sustained stretch and paused naturally for endOfTurnFrames.
        this.voicedFrames >= Math.max(this.config.minimumSpeechFrames * 2, 4) &&
        (this.quietFrames >= this.config.endOfTurnFrames || hardMax)
      ) {
        // Even if STT hasn't returned partials yet, commit if the user clearly
        // spoke for a sustained stretch and has been silent long enough.
        // Backend STT will transcribe from the audio.
        const fingerprint = `silent_commit|${this.voicedFrames}`;
        if (fingerprint !== this.lastCommitFingerprint) {
          this.lastCommitFingerprint = fingerprint;
          speechCommit = true;
          reason = hardMax ? "max_speech_no_partial" : "silence_commit_no_partial";
          this.resetSpeech();
          this.state = "committing";
        } else {
          this.resetSpeech();
          this.state = "listening";
          reason = "noise_rejected";
        }
      }
    } else if (this.hotFrames > 0 && !isBusy) {
      this.state = "possible_speech";
    } else if (input.assistantPlaying) {
      this.state = this.state === "interrupted" ? "interrupted" : "speaking";
    } else if (isBusy) {
      this.state = this.state === "interrupted" ? "interrupted" : "waiting_for_provider";
    } else {
      this.state = "listening";
    }

    if (bargeIn) {
      this.resetSpeech();
      this.state = "interrupted";
      // A barge-in is an interruption, never a turn commit — committing here
      // would send a stale/partial transcript as a fresh user turn.
      speechCommit = false;
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
