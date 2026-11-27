import type { InputSnapshot } from "../types/game.ts";

export interface ControlActionEvent {
  pauseToggled: boolean;
  restartPressed: boolean;
  ghostToggled: boolean;
  muteToggled: boolean;
  debugToggled: boolean;
  checkpointRespawnPressed: boolean;
}

export type TouchActionName = "throttle" | "brake" | "leanLeft" | "leanRight" | "jump" | "boost";

const PREVENT_KEYS = new Set([
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
  "Space",
  "Tab",
]);

export class InputManager {
  private keysDown = new Set<string>();
  private touchActive: Record<TouchActionName, boolean> = {
    throttle: false,
    brake: false,
    leanLeft: false,
    leanRight: false,
    jump: false,
    boost: false,
  };
  private prevJump = false;
  private pendingEvents: ControlActionEvent = {
    pauseToggled: false,
    restartPressed: false,
    ghostToggled: false,
    muteToggled: false,
    debugToggled: false,
    checkpointRespawnPressed: false,
  };
  private onAnyGesture?: () => void;
  private boundKeyDown: (e: KeyboardEvent) => void;
  private boundKeyUp: (e: KeyboardEvent) => void;
  private boundBlur: () => void;

  constructor(onAnyGesture?: () => void) {
    this.onAnyGesture = onAnyGesture;
    this.boundKeyDown = (e) => this.handleKeyDown(e);
    this.boundKeyUp = (e) => this.handleKeyUp(e);
    this.boundBlur = () => this.clearAll();
    if (typeof window !== "undefined") {
      window.addEventListener("keydown", this.boundKeyDown, { passive: false });
      window.addEventListener("keyup", this.boundKeyUp);
      window.addEventListener("blur", this.boundBlur);
    }
  }

  destroy(): void {
    if (typeof window !== "undefined") {
      window.removeEventListener("keydown", this.boundKeyDown);
      window.removeEventListener("keyup", this.boundKeyUp);
      window.removeEventListener("blur", this.boundBlur);
    }
  }

  clearAll(): void {
    this.keysDown.clear();
    for (const k of Object.keys(this.touchActive) as TouchActionName[]) {
      this.touchActive[k] = false;
    }
  }

  setTouchAction(action: TouchActionName, pressed: boolean): void {
    if (pressed) this.onAnyGesture?.();
    this.touchActive[action] = pressed;
  }

  triggerDebugToggle(): void {
    this.pendingEvents.debugToggled = true;
  }

  triggerPauseToggle(): void {
    this.pendingEvents.pauseToggled = true;
  }

  triggerRestart(): void {
    this.pendingEvents.restartPressed = true;
  }

  private handleKeyDown(e: KeyboardEvent): void {
    const tag = (e.target as HTMLElement | null)?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (PREVENT_KEYS.has(e.code)) {
      e.preventDefault();
    }
    this.onAnyGesture?.();
    if (!e.repeat) {
      if (e.code === "Escape" || e.code === "KeyP") this.pendingEvents.pauseToggled = true;
      if (e.code === "KeyR") this.pendingEvents.restartPressed = true;
      if (e.code === "KeyC") this.pendingEvents.checkpointRespawnPressed = true;
      if (e.code === "Tab") this.pendingEvents.ghostToggled = true;
      if (e.code === "KeyM") this.pendingEvents.muteToggled = true;
      if (e.code === "F3" || e.code === "Backquote") this.pendingEvents.debugToggled = true;
    }
    this.keysDown.add(e.code);
  }

  private handleKeyUp(e: KeyboardEvent): void {
    this.keysDown.delete(e.code);
  }

  consumeControlEvents(): ControlActionEvent {
    const out = { ...this.pendingEvents };
    this.pendingEvents = {
      pauseToggled: false,
      restartPressed: false,
      ghostToggled: false,
      muteToggled: false,
      debugToggled: false,
      checkpointRespawnPressed: false,
    };
    return out;
  }

  readSnapshot(): InputSnapshot {
    let throttle = this.keysDown.has("KeyW") || this.keysDown.has("ArrowUp") || this.touchActive.throttle ? 1 : 0;
    let brake = this.keysDown.has("KeyS") || this.keysDown.has("ArrowDown") || this.touchActive.brake ? 1 : 0;
    const left = this.keysDown.has("KeyA") || this.keysDown.has("ArrowLeft") || this.touchActive.leanLeft ? 1 : 0;
    const right = this.keysDown.has("KeyD") || this.keysDown.has("ArrowRight") || this.touchActive.leanRight ? 1 : 0;
    let lean = right - left;
    let jumpHeld = this.keysDown.has("Space") || this.touchActive.jump;
    let boost =
      this.keysDown.has("ShiftLeft") ||
      this.keysDown.has("ShiftRight") ||
      this.keysDown.has("KeyE") ||
      this.touchActive.boost;

    // Poll standard Gamepad if attached
    if (typeof navigator !== "undefined" && typeof navigator.getGamepads === "function") {
      try {
        const pads = navigator.getGamepads();
        for (const pad of pads) {
          if (!pad) continue;
          const rt = pad.buttons[7]?.value ?? 0;
          const lt = pad.buttons[6]?.value ?? 0;
          const axisX = Math.abs(pad.axes[0] ?? 0) > 0.16 ? (pad.axes[0] ?? 0) : 0;
          throttle = Math.max(throttle, rt, pad.buttons[1]?.pressed ? 1 : 0);
          brake = Math.max(brake, lt, pad.buttons[2]?.pressed ? 1 : 0);
          if (Math.abs(axisX) > Math.abs(lean)) lean = axisX;
          if (pad.buttons[0]?.pressed) jumpHeld = true;
          if (pad.buttons[5]?.pressed || pad.buttons[3]?.pressed) boost = true;
          break;
        }
      } catch {
        // ignore sandboxed gamepad permission denials
      }
    }

    const jumpPressed = jumpHeld && !this.prevJump;
    this.prevJump = jumpHeld;
    return { throttle, brake, lean, jumpPressed, jumpHeld, boost };
  }
}
