/** Vertical anatomy markers (world Y) the companion camera needs. */
export interface FramingAnatomy {
  headY: number;
  neckY: number;
  chestY: number;
  hipsY: number;
  minY: number;
  maxY: number;
  width?: number;
}

export interface VerticalSpan { top: number; bottom: number }

/**
 * Panels narrower than this (width / height) are tall docks, not wide stages:
 * the bust crop wastes their height and clips the sleeves, so we frame down to
 * the hands instead.
 */
export const HANDS_FRAMING_MAX_ASPECT = 0.9;
/** Hanging hands sit roughly at hip height, a little below the hips bone. */
const HAND_DROP_TORSO = 0.42;
/** Dock UI (subtitle card, controls) covers the lowest part of narrow panels. */
const OVERLAY_RESERVE = 0.14;

export function framesHands(aspect: number): boolean {
  return Number.isFinite(aspect) && aspect > 0 && aspect < HANDS_FRAMING_MAX_ASPECT;
}

/** Waist-up span that keeps resting and gesturing hands inside the shot. */
export function handsFramingSpan(frame: FramingAnatomy, bustTop: number): VerticalSpan {
  const torso = Math.max(0.28, frame.headY - frame.chestY);
  const handsY = frame.hipsY - torso * HAND_DROP_TORSO;
  const top = bustTop;
  const bottom = handsY - (top - handsY) * OVERLAY_RESERVE;
  return { top, bottom };
}

/** Distance at which a span of `height` and a body `width` both fit the viewport. */
export function fitDistance(height: number, width: number, fovDegrees: number, aspect: number): number {
  const tangent = Math.tan(fovDegrees * Math.PI / 360);
  const vertical = Math.max(0.22, height / 2) * 1.12 / tangent;
  const horizontal = (Math.max(0, width) / 2) * 1.08 / (tangent * Math.max(0.1, aspect));
  return Math.max(0.58, vertical, horizontal);
}
