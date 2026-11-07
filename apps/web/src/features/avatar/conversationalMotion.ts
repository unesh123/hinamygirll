export interface ConversationMotion { pitch: number; yaw: number; roll: number; arm: number; wrist: number }

/** Small rotations around the authored rest pose, with no per-frame allocations. */
export function sampleConversationMotion(time: number, speechEnergy: number, engaged: boolean, out: ConversationMotion): ConversationMotion {
  const energy = Math.max(0, Math.min(1, speechEnergy));
  const emphasis = energy * (0.35 + 0.65 * Math.pow(Math.max(0, Math.sin(time * 2.1)), 2));
  out.yaw = Math.sin(time * 0.42) * 0.045 + Math.sin(time * 0.19 + 1.7) * 0.025;
  out.pitch = Math.sin(time * 0.35 + 0.6) * 0.025 + emphasis * Math.sin(time * 4.2) * 0.035;
  out.roll = Math.sin(time * 0.29 + 2.2) * 0.015 + (engaged ? Math.sin(time * 0.6) * 0.015 : 0);
  out.arm = emphasis * Math.sin(time * 1.1) * 0.025;
  out.wrist = emphasis * Math.sin(time * 1.1 + 0.8) * 0.018;
  return out;
}

/**
 * Per-arm conversational gesture in radians. Values are sign-free magnitudes in
 * the anatomical sense (forward, outward, flexed); the caller mirrors them per
 * side when composing bone rotations.
 */
export interface ArmGesture {
  upperFwd: number;
  upperOut: number;
  elbow: number;
  twist: number;
  wristFlex: number;
  wristDev: number;
  wristTwist: number;
}

export const ARM_GESTURE_LIMITS: Readonly<ArmGesture> = {
  upperFwd: 0.26,
  upperOut: 0.12,
  elbow: 0.95,
  twist: 0.36,
  wristFlex: 0.40,
  wristDev: 0.30,
  wristTwist: 0.30,
};

const TAU = Math.PI * 2;

/**
 * Speech-phrased arm gesture: each hand lifts, hovers and relaxes on its own slow
 * phrase cycle (right hand leads), with a faster syllabic beat on the wrist.
 * Silence leaves only a tiny breathing sway. Allocation-free; pure in `time`.
 * `side` is +1 for the left arm and -1 for the right arm.
 */
export function sampleArmGesture(time: number, speechEnergy: number, side: 1 | -1, out: ArmGesture): ArmGesture {
  const energy = Number.isFinite(speechEnergy) ? Math.max(0, Math.min(1, speechEnergy)) : 0;
  const amp = Math.min(1, energy * 1.8);
  const lead = side < 0;
  const phrase = Math.sin(TAU * (lead ? 0.21 : 0.15) * time + (lead ? 0 : 2.1) + 0.6 * Math.sin(TAU * 0.047 * time));
  const lift = Math.pow(Math.max(0, phrase), 1.4);
  const beat = 0.5 + 0.5 * Math.sin(TAU * (lead ? 2.3 : 1.9) * time + side);
  const g = amp * (lead ? 1 : 0.7) * lift;
  const sway = Math.sin(TAU * 0.11 * time + side * 1.3);
  const breath = Math.sin(TAU * 0.25 * time + side * 0.5);

  out.upperFwd = 0.03 * sway + g * 0.20;
  out.upperOut = 0.02 * breath + g * 0.08;
  out.elbow = 0.04 * (0.5 + 0.5 * sway) + g * (0.70 + 0.12 * beat);
  out.twist = 0.02 * sway + g * 0.30;
  out.wristFlex = 0.03 * Math.sin(TAU * 0.17 * time + side) + g * 0.18 + amp * lift * 0.12 * (beat - 0.5) * 2;
  out.wristDev = 0.02 * Math.sin(TAU * 0.13 * time + side * 2) + amp * lift * 0.20 * Math.sin(TAU * 1.3 * time + side);
  out.wristTwist = 0.02 * breath + g * 0.20;
  return out;
}
