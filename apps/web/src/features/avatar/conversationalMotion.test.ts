import { describe, expect, it } from "vitest";
import { sampleConversationMotion } from "./conversationalMotion";
describe("conversational rig movement", () => {
  it("keeps motion bounded and does not allocate an output per frame", () => {
    const pose = { pitch:0, yaw:0, roll:0, arm:0, wrist:0 };
    for(let frame=0;frame<3600;frame++) {
      expect(sampleConversationMotion(frame/60, frame%2 ? 10 : -10, true, pose)).toBe(pose);
      expect(Math.abs(pose.pitch)).toBeLessThanOrEqual(.061);
      expect(Math.abs(pose.yaw)).toBeLessThanOrEqual(.071);
      expect(Math.abs(pose.arm)).toBeLessThanOrEqual(.026);
      expect(Math.abs(pose.wrist)).toBeLessThanOrEqual(.019);
    }
  });
  it("keeps limbs in their rest pose during silence", () => {
    const pose={pitch:0,yaw:0,roll:0,arm:0,wrist:0};
    sampleConversationMotion(2, 0, false, pose);
    expect(pose.arm).toBe(0); expect(pose.wrist).toBe(0);
  });
});

import { ARM_GESTURE_LIMITS, sampleArmGesture, type ArmGesture } from "./conversationalMotion";

const blankGesture = (): ArmGesture => ({ upperFwd: 0, upperOut: 0, elbow: 0, twist: 0, wristFlex: 0, wristDev: 0, wristTwist: 0 });

describe("arm gesture sampler", () => {
  it("stays within anatomical limits for any energy and never allocates", () => {
    const out = blankGesture();
    for (const side of [1, -1] as const) {
      for (let frame = 0; frame < 7200; frame++) {
        const energy = [0, 0.35, 1, 10, -3, Number.NaN][frame % 6];
        expect(sampleArmGesture(frame / 60, energy, side, out)).toBe(out);
        for (const key of Object.keys(ARM_GESTURE_LIMITS) as Array<keyof ArmGesture>) {
          expect(Number.isFinite(out[key])).toBe(true);
          expect(Math.abs(out[key])).toBeLessThanOrEqual(ARM_GESTURE_LIMITS[key]);
        }
      }
    }
  });

  it("lifts the forearm visibly while speaking and only sways while silent", () => {
    for (const side of [1, -1] as const) {
      const out = blankGesture();
      let speakingPeak = 0;
      let silentPeak = 0;
      for (let frame = 0; frame < 60 * 30; frame++) {
        sampleArmGesture(frame / 60, 0.6, side, out);
        speakingPeak = Math.max(speakingPeak, out.elbow);
        sampleArmGesture(frame / 60, 0, side, out);
        silentPeak = Math.max(silentPeak, out.elbow, out.upperFwd, out.wristFlex);
      }
      expect(speakingPeak).toBeGreaterThan(0.35);
      expect(silentPeak).toBeLessThan(0.06);
    }
  });

  it("moves smoothly between frames (no jitter)", () => {
    const prev = blankGesture();
    const cur = blankGesture();
    sampleArmGesture(0, 1, -1, prev);
    for (let frame = 1; frame < 60 * 20; frame++) {
      sampleArmGesture(frame / 60, 1, -1, cur);
      expect(Math.abs(cur.elbow - prev.elbow)).toBeLessThan(0.05);
      expect(Math.abs(cur.wristFlex - prev.wristFlex)).toBeLessThan(0.05);
      Object.assign(prev, cur);
    }
  });

  it("alternates hands instead of mirroring them", () => {
    const left = blankGesture();
    const right = blankGesture();
    let differing = 0;
    for (let frame = 0; frame < 60 * 20; frame++) {
      sampleArmGesture(frame / 60, 0.8, 1, left);
      sampleArmGesture(frame / 60, 0.8, -1, right);
      if (Math.abs(left.elbow - right.elbow) > 0.2) differing++;
    }
    expect(differing).toBeGreaterThan(60);
  });
});
