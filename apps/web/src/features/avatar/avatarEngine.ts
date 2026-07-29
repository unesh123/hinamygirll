import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionId, CompanionState } from "../companion/types";

export interface AvatarEngineFrame {
  companionId: CompanionId;
  state: CompanionState;
  plan?: AssistantTurnPlan;
  reducedMotion: boolean;
  textOnly: boolean;
}

export interface AvatarEngine {
  readonly id: string;
  readonly kind: "procedural-placeholder" | "vrm";
  getFrame(frame: AvatarEngineFrame): AvatarEngineFrame;
}

export class ProceduralAvatarEngine implements AvatarEngine {
  readonly id = "procedural-avatar-v1";
  readonly kind = "procedural-placeholder" as const;

  getFrame(frame: AvatarEngineFrame): AvatarEngineFrame {
    return frame;
  }
}
