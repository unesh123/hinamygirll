export interface BlinkShapeSpec {
  /** Peak lid closure 0-1. Full blinks approach 1; partial blinks stay low. */
  peak: number;
  /** Seconds to close. */
  close: number;
  /** Seconds to reopen. */
  open: number;
  /** Right-lid multiplier for slight natural asymmetry. */
  asym: number;
}

/**
 * Rolls the shape of the next blink. Human blinks close the lids fully about
 * four times out of five — only the occasional blink is partial. A uniform
 * mid-range peak never lets the eyes actually shut and reads as a stiff
 * "3D character" flutter, so the distribution is bimodal on purpose.
 * Drowsiness lengthens both phases and adds weight to partial blinks.
 */
export function rollBlinkShapeSpec(
  drowsyHeavy: number,
  rng: () => number = Math.random,
): BlinkShapeSpec {
  const fullClose = rng() < 0.78;
  return {
    peak: fullClose
      ? 0.86 + rng() * 0.14
      : 0.48 + rng() * 0.24 + drowsyHeavy * 0.08,
    close: (0.100 + rng() * 0.050) * (1 + drowsyHeavy * 0.5),
    open: (0.065 + rng() * 0.035) * (1 + drowsyHeavy * 0.4),
    asym: 0.90 + rng() * 0.16,
  };
}
