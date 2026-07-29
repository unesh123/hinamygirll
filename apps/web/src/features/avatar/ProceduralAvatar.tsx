import type { CSSProperties } from "react";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionId, CompanionState } from "../companion/types";
import { ProceduralAvatarEngine } from "./avatarEngine";

interface ProceduralAvatarProps {
  companionId: CompanionId;
  state: CompanionState;
  plan?: AssistantTurnPlan;
  reducedMotion: boolean;
  textOnly: boolean;
  jawEnergy?: number;
}

const engine = new ProceduralAvatarEngine();

export function ProceduralAvatar(props: ProceduralAvatarProps) {
  const frame = engine.getFrame(props);
  const emotion = frame.plan?.emotion.primary ?? "neutral";
  const gesture = frame.plan?.performance.gesture ?? "none";

  if (frame.textOnly) {
    return (
      <div className="avatar-fallback" data-testid="text-only-avatar">
        <span aria-hidden="true">✦</span>
        <strong>Text-only mode</strong>
        <small>
          Avatar motion is paused. Conversation controls still work.
        </small>
      </div>
    );
  }

  return (
    <div
      className={`procedural-stage accent-${frame.companionId} state-${frame.state} emotion-${emotion} gesture-${gesture}`}
      style={{ "--jaw-energy": frame.jawEnergy ?? 0 } as CSSProperties}
      data-engine={engine.id}
      data-state={frame.state}
      data-emotion={emotion}
      data-reduced-motion={String(frame.reducedMotion)}
      aria-hidden="true"
    >
      <div className="ambient-orb orb-one" />
      <div className="ambient-orb orb-two" />
      <div className="avatar-shadow" />
      <div className="avatar-body">
        <div className="avatar-neck" />
        <div className="avatar-head">
          <div className="avatar-hair hair-back" />
          <div className="avatar-ear ear-left" />
          <div className="avatar-ear ear-right" />
          <div className="avatar-face">
            <div className="avatar-brow brow-left" />
            <div className="avatar-brow brow-right" />
            <div className="avatar-eye eye-left">
              <span />
            </div>
            <div className="avatar-eye eye-right">
              <span />
            </div>
            <div className="avatar-nose" />
            <div className="avatar-mouth" />
            <div className="avatar-blush blush-left" />
            <div className="avatar-blush blush-right" />
          </div>
          <div className="avatar-hair hair-front" />
        </div>
        <div className="avatar-torso">
          <div className="collar collar-left" />
          <div className="collar collar-right" />
        </div>
        <div className="avatar-hand" />
      </div>
      <div className="state-ripple ripple-one" />
      <div className="state-ripple ripple-two" />
    </div>
  );
}
