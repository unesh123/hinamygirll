/** Fit both axes of the body, including walk travel and space for dock controls. */
export function fullBodyCameraDistance(
  height: number,
  width: number,
  aspect: number,
  fovDegrees = 43,
  depth = 0,
): number {
  const tangent = Math.tan(fovDegrees * Math.PI / 360);
  const vertical = Math.max(1.1, height) * 0.5 / tangent;
  const horizontal = (Math.max(0.4, width) + 0.56) * 0.5 / (tangent * Math.max(0.1, aspect));
  return Math.max(vertical, horizontal) * 1.35 + Math.max(0, depth) * 0.5;
}
