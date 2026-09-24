/**
 * HINA MOTION SYSTEM — "THE WALK"
 *
 * Core philosophy:
 * The UI is never static. It is either resting, breathing, or walking.
 * Nothing appears. Nothing disappears. Everything TRANSFORMS from what was already there.
 *
 * LAW 2: The Motion Vocabulary (only 5 presets, never more)
 * LAW 3: The Timing Bible (hardcoded exact timings)
 */

import type { Transition, TargetAndTransition } from "framer-motion";

export const HINA_TIMINGS = {
  pillIdleBreathing: 2400,
  intentDetectedToCard: 220,
  fieldCascadePerChild: 40,
  localValueTick: 140,
  enterCommitSquash: 160,
  cardDropToStack: 200,
  oldRowsPushDown: 200,
  escCollapseToPill: 180,
  historyRowExpand: 260,
  pipelineNodeLight: 320,
  thinkingRailLineAppear: 120,
  localParseDebounce: 40, // < 80ms perceived local parse
  modelEscalationDelay: 420, // 420ms typing pause before LLM fallback
} as const;

export const HINA_MOTION = {
  // 1. TICK — value changed locally (e.g. ₹800 → ₹600, dice roll, copy)
  tick: {
    scale: [1, 1.08, 1],
    transition: {
      duration: 0.14,
      ease: "easeOut",
    },
  } as TargetAndTransition,

  // 2. SPRING — pill becomes card (intent detected)
  spring: {
    type: "spring",
    stiffness: 520,
    damping: 34,
    mass: 0.9,
  } as Transition,

  // 3. STAGGER — chips/fields rise in sequence (8px rise, 40ms stagger)
  stagger: {
    childY: 8,
    childOpacity: [0, 1],
    delayPerChild: 0.04,
    duration: 0.18,
  },

  // 4. SETTLE — card commits, stack slides down as one body (expo-out)
  settle: {
    type: "tween",
    duration: 0.2,
    ease: [0.22, 1, 0.36, 1], // Expo-out curve
  } as Transition,

  // 5. PULSE — pipeline node lights up / honest progress
  pulse: {
    scale: [1, 1.04, 1],
    transition: {
      duration: 0.32,
      ease: "easeOut",
    },
  } as TargetAndTransition,

  // Breathing pill for idle state
  breathing: {
    scale: [1.0, 1.015, 1.0],
    transition: {
      duration: 2.4,
      repeat: Infinity,
      ease: "easeInOut",
    },
  } as TargetAndTransition,

  // Error shake
  errorShake: {
    x: [0, -3, 3, -3, 3, 0],
    transition: {
      duration: 0.18,
      ease: "easeInOut",
    },
  } as TargetAndTransition,

  // Reduced motion instant snap fallback
  reducedSnap: {
    duration: 0.01,
  } as Transition,
};

/**
 * Returns either the spring transition or an instant snap if user prefers reduced motion.
 */
export function getHinaTransition(prefersReducedMotion: boolean | null, type: "spring" | "settle" = "spring"): Transition {
  if (prefersReducedMotion) {
    return HINA_MOTION.reducedSnap;
  }
  return type === "settle" ? HINA_MOTION.settle : HINA_MOTION.spring;
}
