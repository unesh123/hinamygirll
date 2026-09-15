import type { VrmExpressionWeights } from "./vrmExpressionMap";
import { LipSyncRuntime } from "./lipSyncRuntime";
import type { SpeechTimingSource } from "../audio/speechTimingSource";
import type { VisemeEvent } from "../audio/textToViseme";

export type PerformanceState =
  | "IDLE"
  | "LISTENING"
  | "THINKING"
  | "WORKING"
  | "SPEAKING"
  | "REACTING"
  | "INTERRUPTED";

export interface GazeTarget {
  x: number;
  y: number;
  z: number;
  confidence: number;
}

export interface HeadRotation {
  x: number;
  y: number;
  z: number;
}

export interface ArmPose {
  leftArm: { x: number; y: number; z: number };
  rightArm: { x: number; y: number; z: number };
  leftLowerArm?: { x: number; y: number; z: number };
  rightLowerArm?: { x: number; y: number; z: number };
}

export interface PerformanceSubstrateOutput {
  state: PerformanceState;
  emotion: string;
  intensity: number;
  gaze: GazeTarget;
  head: HeadRotation;
  arms: ArmPose;
  blinking: boolean;
  lipSync: {
    aa: number;
    ih: number;
    ou: number;
    ee: number;
    oh: number;
    jawOpen: number;
  };
  expressions: Partial<VrmExpressionWeights>;
}

// ── 1. EmotionRuntime ────────────────────────────────────────────────────────
export class EmotionRuntime {
  private currentEmotion = "neutral";
  private intensity = 0.5;

  setEmotion(emotion: string, intensity = 0.5): void {
    this.currentEmotion = emotion || "neutral";
    this.intensity = Math.max(0, Math.min(intensity, 1));
  }

  getEmotion(): string {
    return this.currentEmotion;
  }

  getIntensity(): number {
    return this.intensity;
  }
}

// ── 2. BlinkRuntime ──────────────────────────────────────────────────────────
export class BlinkRuntime {
  private nextBlinkTime = 3.0;
  private blinkDuration = 0.15;
  private blinkProgress = -1; // -1 = not blinking, 0..1 = blinking
  private isDoubleBlink = false;

  update(deltaSeconds: number, timeSeconds: number, isSuppressed = false): boolean {
    if (isSuppressed) {
      this.blinkProgress = -1;
      return false;
    }

    if (this.blinkProgress >= 0) {
      this.blinkProgress += deltaSeconds / this.blinkDuration;
      if (this.blinkProgress >= 1) {
        if (this.isDoubleBlink) {
          this.isDoubleBlink = false;
          this.blinkProgress = 0; // immediate second blink
        } else {
          this.blinkProgress = -1;
          this.scheduleNext(timeSeconds);
        }
      }
      return true;
    }

    if (timeSeconds >= this.nextBlinkTime) {
      this.blinkProgress = 0;
      this.isDoubleBlink = Math.random() < 0.18; // 18% chance of double blink
      return true;
    }

    return false;
  }

  private scheduleNext(timeSeconds: number): void {
    // Random interval between 2.5 and 5.5 seconds
    const interval = 2.5 + Math.random() * 3.0;
    this.nextBlinkTime = timeSeconds + interval;
  }

  reset(timeSeconds = 0): void {
    this.blinkProgress = -1;
    this.isDoubleBlink = false;
    this.scheduleNext(timeSeconds);
  }
}

// ── 3. GazeRuntime ───────────────────────────────────────────────────────────
export class GazeRuntime {
  private lookTarget: GazeTarget = { x: 0, y: 0.05, z: 1, confidence: 1 };

  update(
    state: PerformanceState,
    emotion: string,
    timeSeconds: number,
    codeMode = false
  ): GazeTarget {
    let x = Math.sin(timeSeconds * 0.4) * 0.15;
    let y = 0.05;
    let z = 1.0;

    switch (state) {
      case "LISTENING":
        // Soft attentive focus on user with micro-drift
        x = Math.sin(timeSeconds * 0.8) * 0.05;
        y = 0.08;
        z = 1.4;
        break;
      case "THINKING":
        // Averts gaze up and sideways thoughtfully
        x = Math.sin(timeSeconds * 0.7) * 0.45;
        y = -0.06;
        z = 1.0;
        break;
      case "WORKING":
        if (codeMode) {
          // Looks rightward toward code workspace
          x = 0.5 + Math.sin(timeSeconds * 0.5) * 0.1;
          y = 0.04;
        }
        break;
      default:
        if (emotion === "shy") {
          x = 0;
          y = -0.2;
        } else if (emotion === "surprised") {
          x = 0;
          y = 0.12;
        } else if (emotion === "sad") {
          y = -0.15;
        }
        break;
    }

    this.lookTarget = {
      x: Math.max(-0.6, Math.min(0.6, x)),
      y: Math.max(-0.35, Math.min(0.3, y)),
      z: Math.max(0.8, z),
      confidence: 1.0,
    };
    return this.lookTarget;
  }
}

// ── 4. Gesture & Posture Runtime ─────────────────────────────────────────────
export class PostureRuntime {
  update(
    state: PerformanceState,
    gesture: string,
    timeSeconds: number,
    intensity = 1.0,
    isVrm1 = true
  ): { head: HeadRotation; arms: ArmPose } {
    const quiet = state === "LISTENING";
    const idleY = quiet
      ? Math.sin(timeSeconds * 0.8) * 0.005
      : Math.sin(timeSeconds * 0.5) * 0.02;
    const microRoll = Math.sin(timeSeconds * 0.37 + 2) * 0.0025;

    let headX = quiet ? 0.08 : 0;
    let headY = quiet ? 0 : idleY;
    let headZ = quiet ? 0.05 : microRoll;

    if (gesture === "small_nod") {
      headX += Math.sin(timeSeconds * 8) * 0.12 * intensity;
    }

    const armZSign = isVrm1 ? -1 : 1;
    const arms: ArmPose = {
      leftArm: { x: 0, y: 0, z: 0 },
      rightArm: { x: 0, y: 0, z: 0 },
    };

    if (gesture === "wave") {
      arms.rightArm = { x: -0.6, y: 0, z: -0.95 * armZSign };
      arms.rightLowerArm = { x: 0, y: -1.25, z: 0 };
    } else if (gesture === "celebrate") {
      arms.leftArm = { x: -0.8, y: 0, z: 1.8 * armZSign };
      arms.rightArm = { x: -0.8, y: 0, z: -1.8 * armZSign };
    }

    return {
      head: { x: headX, y: headY, z: headZ },
      arms,
    };
  }
}

// ── 5. PerformanceDirector (Orchestrator) ─────────────────────────────────────
export class PerformanceDirector {
  private state: PerformanceState = "IDLE";
  readonly emotionRuntime = new EmotionRuntime();
  readonly blinkRuntime = new BlinkRuntime();
  readonly gazeRuntime = new GazeRuntime();
  readonly postureRuntime = new PostureRuntime();
  readonly lipSyncRuntime = new LipSyncRuntime();

  getState(): PerformanceState {
    return this.state;
  }

  setState(newState: PerformanceState): void {
    if (this.state !== newState) {
      this.state = newState;
      if (newState === "INTERRUPTED") {
        this.lipSyncRuntime.reset();
      }
    }
  }

  update(
    deltaSeconds: number,
    timeSeconds: number,
    options: {
      gesture?: string;
      codeMode?: boolean;
      timingSource?: SpeechTimingSource | null;
      fallbackVisemes?: VisemeEvent[];
      jawEnergy?: number;
      isVrm1?: boolean;
    } = {}
  ): PerformanceSubstrateOutput {
    const isSpeaking = this.state === "SPEAKING";
    const emotion = this.emotionRuntime.getEmotion();
    const intensity = this.emotionRuntime.getIntensity();

    // 1. Blinking
    const blinking = this.blinkRuntime.update(deltaSeconds, timeSeconds, false);

    // 2. Gaze
    const gaze = this.gazeRuntime.update(this.state, emotion, timeSeconds, options.codeMode);

    // 3. Posture & Gestures
    const { head, arms } = this.postureRuntime.update(
      this.state,
      options.gesture || "none",
      timeSeconds,
      intensity,
      options.isVrm1 ?? true
    );

    // 4. Lip-sync
    const lipSyncWeights = this.lipSyncRuntime.update(deltaSeconds, options.timingSource ?? null, {
      fallbackVisemes: options.fallbackVisemes,
      jawEnergy: options.jawEnergy,
      speaking: isSpeaking,
    });

    return {
      state: this.state,
      emotion,
      intensity,
      gaze,
      head,
      arms,
      blinking,
      lipSync: lipSyncWeights,
      expressions: {
        aa: lipSyncWeights.aa,
        ih: lipSyncWeights.ih,
        ou: lipSyncWeights.ou,
        ee: lipSyncWeights.ee,
        oh: lipSyncWeights.oh,
        blink: blinking ? 1 : 0,
      },
    };
  }
}
