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
