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
