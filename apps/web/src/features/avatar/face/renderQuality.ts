export type ToneMappingChoice = "aces" | "agx" | "none";

export interface RenderQualityInput {
  reducedMotion?: boolean;
  lowPower?: boolean;
  deviceMemoryGb?: number;
  hardwareConcurrency?: number;
  devicePixelRatio?: number;
  /** Realistic GLB humans benefit from AgX and soft shadows; toon VRMs keep ACES and no shadows. */
  realistic?: boolean;
}

export interface RenderQuality {
  dpr: number;
  shadows: boolean;
  shadowMapSize: number;
  toneMapping: ToneMappingChoice;
  /** Gate for optional DoF/bloom passes; no postprocessing dependency ships yet. */
  postprocessing: boolean;
  lowPower: boolean;
  reducedMotion: boolean;
}

/** Heuristic low-power detection; callers may also pass an explicit user setting. */
export function isLowPowerDevice(i: RenderQualityInput): boolean {
  if (i.lowPower !== undefined) return i.lowPower;
  return (i.deviceMemoryGb !== undefined && i.deviceMemoryGb <= 4)
    || (i.hardwareConcurrency !== undefined && i.hardwareConcurrency <= 4);
}

export function resolveRenderQuality(i: RenderQualityInput = {}): RenderQuality {
  const lowPower = isLowPowerDevice(i);
  const nativeDpr = Math.max(1, i.devicePixelRatio ?? 1);
  const dpr = lowPower ? 1 : Math.min(nativeDpr, i.reducedMotion ? 1.25 : 2);
  return {
    dpr,
    shadows: !lowPower && !!i.realistic,
    shadowMapSize: lowPower ? 512 : 2048,
    toneMapping: i.realistic ? "agx" : "aces",
    postprocessing: !lowPower && !i.reducedMotion,
    lowPower,
    reducedMotion: !!i.reducedMotion,
  };
}

export const LOW_POWER_STORAGE_KEY = "hinaa.low-power";

/** Read device hints, prefers-reduced-motion and the optional `hinaa.low-power=1` override. */
export function readEnvironmentQuality(realistic: boolean): RenderQuality {
  if (typeof window === "undefined") return resolveRenderQuality({ realistic });
  let override: boolean | undefined;
  try {
    const v = window.localStorage.getItem(LOW_POWER_STORAGE_KEY);
    if (v === "1") override = true;
    else if (v === "0") override = false;
  } catch { /* storage may be unavailable */ }
  const nav = navigator as Navigator & { deviceMemory?: number };
  return resolveRenderQuality({
    realistic,
    lowPower: override,
    reducedMotion: typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    deviceMemoryGb: nav.deviceMemory,
    hardwareConcurrency: nav.hardwareConcurrency,
    devicePixelRatio: window.devicePixelRatio,
  });
}
