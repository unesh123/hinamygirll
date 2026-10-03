/**
 * HINAA Creative OS — Universal Tactile UI Sound & Haptic Engine
 * Synthesizes crisp, responsive mechanical clicks, pops, whooshes, chimes,
 * and button presses using the Web Audio API with 0ms latency and 0 external assets.
 */

export type UiSoundType =
  | "click"
  | "buttonPress"
  | "pop"
  | "whoosh"
  | "switch"
  | "success"
  | "deny"
  | "warning"
  | "type";

let audioCtx: AudioContext | null = null;
let soundEnabled = true;

// Initialize sound preference from localStorage
if (typeof window !== "undefined") {
  try {
    const saved = window.localStorage.getItem("hinaa-sound-fx");
    soundEnabled = saved !== "false";
  } catch {
    soundEnabled = true;
  }
}

function getAudioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
  if (!AudioContextClass) return null;

  if (!audioCtx) {
    audioCtx = new AudioContextClass();
  }
  if (audioCtx.state === "suspended") {
    // Attempt resume on user gesture
    void audioCtx.resume();
  }
  return audioCtx;
}

export function isSoundEnabled(): boolean {
  return soundEnabled;
}

export function setSoundEnabled(enabled: boolean): void {
  soundEnabled = enabled;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem("hinaa-sound-fx", enabled ? "true" : "false");
      window.dispatchEvent(new CustomEvent("hinaa-sound-toggle", { detail: { enabled } }));
    } catch {
      // Ignore localStorage errors
    }
  }
  if (enabled) {
    playUiSound("pop");
  }
}

/**
 * Play a synthesized tactile UI sound effect
 */
export function playUiSound(type: UiSoundType = "click"): void {
  if (!soundEnabled) return;

  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    switch (type) {
      case "click": {
        // High-precision mechanical tactile click (Adobe/Leica style)
        osc.type = "triangle";
        osc.frequency.setValueAtTime(920, now);
        osc.frequency.exponentialRampToValueAtTime(340, now + 0.035);
        gain.gain.setValueAtTime(0.09, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.035);
        osc.start(now);
        osc.stop(now + 0.035);
        break;
      }

      case "buttonPress": {
        // Deeper mechanical button latch press
        osc.type = "sine";
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(220, now + 0.045);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.045);
        osc.start(now);
        osc.stop(now + 0.045);
        break;
      }

      case "pop": {
        // Playful Coucou / Hina Island dynamic bubble pop
        osc.type = "sine";
        osc.frequency.setValueAtTime(540, now);
        osc.frequency.exponentialRampToValueAtTime(960, now + 0.07);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.07);
        osc.start(now);
        osc.stop(now + 0.07);
        break;
      }

      case "whoosh": {
        // Sleek panel slide / drawer expand whoosh
        osc.type = "sine";
        osc.frequency.setValueAtTime(260, now);
        osc.frequency.exponentialRampToValueAtTime(620, now + 0.12);
        gain.gain.setValueAtTime(0.09, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
        osc.start(now);
        osc.stop(now + 0.12);
        break;
      }

      case "switch": {
        // Micro-chirp toggle switch tick
        osc.type = "triangle";
        osc.frequency.setValueAtTime(1400, now);
        osc.frequency.exponentialRampToValueAtTime(800, now + 0.025);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.025);
        osc.start(now);
        osc.stop(now + 0.025);
        break;
      }

      case "success": {
        // Harmonic major triad chime (C5 -> E5 -> G5)
        const chimeTimes = [now, now + 0.06, now + 0.12];
        const freqs = [523.25, 659.25, 783.99];

        freqs.forEach((f, idx) => {
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.type = "sine";
          o.frequency.setValueAtTime(f, chimeTimes[idx]);
          o.connect(g);
          g.connect(ctx.destination);
          g.gain.setValueAtTime(0.08, chimeTimes[idx]);
          g.gain.exponentialRampToValueAtTime(0.001, chimeTimes[idx] + 0.18);
          o.start(chimeTimes[idx]);
          o.stop(chimeTimes[idx] + 0.18);
        });
        break;
      }

      case "deny": {
        // Cautionary double low buzz
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(220, now);
        osc.frequency.setValueAtTime(160, now + 0.08);
        gain.gain.setValueAtTime(0.1, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.16);
        osc.start(now);
        osc.stop(now + 0.16);
        break;
      }

      case "warning": {
        // Alert chime
        osc.type = "sine";
        osc.frequency.setValueAtTime(680, now);
        osc.frequency.setValueAtTime(540, now + 0.08);
        gain.gain.setValueAtTime(0.11, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
        osc.start(now);
        osc.stop(now + 0.15);
        break;
      }

      case "type": {
        // Ultra subtle typing tick
        osc.type = "triangle";
        osc.frequency.setValueAtTime(1100, now);
        gain.gain.setValueAtTime(0.03, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.015);
        osc.start(now);
        osc.stop(now + 0.015);
        break;
      }
    }
  } catch {
    // Autoplay policy or AudioContext unavailable
  }
}

/**
 * Universal Global Click & Tactile Sound Delegator
 * Automatically triggers tactile click feedback for any button, role="button",
 * link, or interactive tab across the entire dashboard.
 */
let isListenerAttached = false;

export function initGlobalUiSounds(): () => void {
  if (typeof window === "undefined" || isListenerAttached) {
    return () => {};
  }

  isListenerAttached = true;

  const handleClick = (e: MouseEvent) => {
    const target = e.target as HTMLElement | null;
    if (!target) return;

    // Check if element or any ancestor is interactive
    const interactive = target.closest<HTMLElement>(
      'button, [role="button"], [role="tab"], [role="menuitem"], a[href], input[type="checkbox"], input[type="radio"], [data-sound]'
    );

    if (interactive) {
      const explicitSound = interactive.getAttribute("data-sound") as UiSoundType | null;
      playUiSound(explicitSound || "click");
    }
  };

  document.addEventListener("click", handleClick, { capture: true, passive: true });

  return () => {
    document.removeEventListener("click", handleClick, { capture: true });
    isListenerAttached = false;
  };
}
