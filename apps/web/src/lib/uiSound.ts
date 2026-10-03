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
  | "type"
  | "send"
  | "step"
  | "mochiPoke"
  | "mochiDizzy"
  | "mochiLove"
  | "mochiEat"
  | "streamChunk";

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

// Throttling timer for real-time generative streaming audio
let lastStreamChunkSoundTime = 0;

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
        // High-precision mechanical key clack with organic pitch jitter
        const jitter = (Math.random() - 0.5) * 160;
        osc.type = "triangle";
        osc.frequency.setValueAtTime(940 + jitter, now);
        osc.frequency.exponentialRampToValueAtTime(320 + jitter * 0.4, now + 0.024);
        gain.gain.setValueAtTime(0.06, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.024);
        osc.start(now);
        osc.stop(now + 0.024);

        // Subtle bottom-out thump layer
        const subOsc = ctx.createOscillator();
        const subGain = ctx.createGain();
        subOsc.type = "sine";
        subOsc.frequency.setValueAtTime(160, now);
        subOsc.frequency.exponentialRampToValueAtTime(60, now + 0.02);
        subGain.gain.setValueAtTime(0.04, now);
        subGain.gain.exponentialRampToValueAtTime(0.001, now + 0.02);
        subOsc.connect(subGain);
        subGain.connect(ctx.destination);
        subOsc.start(now);
        subOsc.stop(now + 0.02);
        break;
      }

      case "send": {
        // Sci-fi message transmit whoosh / digital launch pulse
        osc.type = "sine";
        osc.frequency.setValueAtTime(320, now);
        osc.frequency.exponentialRampToValueAtTime(1150, now + 0.09);
        osc.frequency.exponentialRampToValueAtTime(840, now + 0.14);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.14);
        osc.start(now);
        osc.stop(now + 0.14);

        // High shimmer overtone
        const overtone = ctx.createOscillator();
        const overGain = ctx.createGain();
        overtone.type = "triangle";
        overtone.frequency.setValueAtTime(860, now + 0.02);
        overtone.frequency.exponentialRampToValueAtTime(1800, now + 0.1);
        overGain.gain.setValueAtTime(0.05, now + 0.02);
        overGain.gain.exponentialRampToValueAtTime(0.001, now + 0.1);
        overtone.connect(overGain);
        overGain.connect(ctx.destination);
        overtone.start(now + 0.02);
        overtone.stop(now + 0.1);
        break;
      }

      case "step": {
        // Crisp shoe/paw footstep tap for walking locomotion
        const stepPitch = 220 + (Math.random() - 0.5) * 50;
        osc.type = "triangle";
        osc.frequency.setValueAtTime(stepPitch, now);
        osc.frequency.exponentialRampToValueAtTime(80, now + 0.028);
        gain.gain.setValueAtTime(0.05, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.028);
        osc.start(now);
        osc.stop(now + 0.028);
        break;
      }

      case "streamChunk": {
        // Generative text decoding blip (subtle sci-fi teletype chatter)
        const blipFreq = 1650 + Math.random() * 550;
        osc.type = "sine";
        osc.frequency.setValueAtTime(blipFreq, now);
        gain.gain.setValueAtTime(0.022, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.012);
        osc.start(now);
        osc.stop(now + 0.012);
        break;
      }

      case "mochiPoke": {
        // Annoyed squeak / chirp when mascot is poked
        osc.type = "sine";
        osc.frequency.setValueAtTime(740, now);
        osc.frequency.exponentialRampToValueAtTime(1180, now + 0.04);
        osc.frequency.exponentialRampToValueAtTime(860, now + 0.09);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.09);
        osc.start(now);
        osc.stop(now + 0.09);
        break;
      }

      case "mochiDizzy": {
        // Dizzy wobble sound after 3+ pokes
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(520, now);
        osc.frequency.exponentialRampToValueAtTime(260, now + 0.28);
        gain.gain.setValueAtTime(0.08, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
        osc.start(now);
        osc.stop(now + 0.28);
        break;
      }

      case "mochiLove": {
        // Sparkly heart chime when mascot feels loved
        const loveTimes = [now, now + 0.05];
        const loveFreqs = [880, 1318.5]; // A5 -> E6
        loveFreqs.forEach((f, idx) => {
          const o = ctx.createOscillator();
          const g = ctx.createGain();
          o.type = "sine";
          o.frequency.setValueAtTime(f, loveTimes[idx]);
          o.connect(g);
          g.connect(ctx.destination);
          g.gain.setValueAtTime(0.09, loveTimes[idx]);
          g.gain.exponentialRampToValueAtTime(0.001, loveTimes[idx] + 0.22);
          o.start(loveTimes[idx]);
          o.stop(loveTimes[idx] + 0.22);
        });
        break;
      }

      case "mochiEat": {
        // Gulp / munch pop when dropped file is eaten
        osc.type = "sine";
        osc.frequency.setValueAtTime(460, now);
        osc.frequency.exponentialRampToValueAtTime(180, now + 0.08);
        gain.gain.setValueAtTime(0.14, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
        osc.start(now);
        osc.stop(now + 0.08);
        break;
      }
    }
  } catch {
    // Autoplay policy or AudioContext unavailable
  }
}

/**
 * Dedicated helper to play mechanical keyboard typing sounds on keydown
 */
export function playTypingSound(_key?: string): void {
  playUiSound("type");
}

/**
 * Dedicated helper to play sending / transmit audio
 */
export function playSendSound(): void {
  playUiSound("send");
}

/**
 * Dedicated helper to play footstep tap during walking locomotion
 */
export function playFootstepSound(): void {
  playUiSound("step");
}

/**
 * Dedicated throttled helper for real-time generative streaming text tokens
 */
export function playStreamChunkSound(): void {
  const now = typeof performance !== "undefined" ? performance.now() : Date.now();
  if (now - lastStreamChunkSoundTime < 65) return; // 65ms throttle for smooth teletype rhythm
  lastStreamChunkSoundTime = now;
  playUiSound("streamChunk");
}

/**
 * Helper for mascot poke reaction
 */
export function playMochiPoke(count = 1): void {
  if (count >= 3) {
    playUiSound("mochiDizzy");
  } else {
    playUiSound("mochiPoke");
  }
}

/**
 * Helper for mascot heart affection
 */
export function playMochiLove(): void {
  playUiSound("mochiLove");
}

/**
 * Helper for mascot file swallowing
 */
export function playMochiEat(): void {
  playUiSound("mochiEat");
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
