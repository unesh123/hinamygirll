import { useEffect, useMemo, useRef, useState } from "react";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import {
  PerformanceScheduler,
  type ActivePerformanceFrame,
  type PerformanceTier,
} from "./performanceScheduler";

/** FPS windows below which the tier auto-downgrades (sticky, never oscillates). */
const TIER_DOWNGRADE_FPS: Partial<Record<PerformanceTier, number>> = {
  high: 30,
  medium: 24,
};
const FPS_SAMPLE_WINDOW_MS = 5_000;

export function usePerformanceClock(options: {
  plan?: AssistantTurnPlan;
  jawEnergy?: number;
  reducedMotion: boolean;
  interrupted: boolean;
  /** Explicit tier override (e.g. user battery-saver). When set, auto-degradation is disabled. */
  tier?: PerformanceTier;
}) {
  const scheduler = useMemo(() => new PerformanceScheduler(), []);
  const [frame, setFrame] = useState<ActivePerformanceFrame>(() =>
    scheduler.sample(),
  );
  const [autoTier, setAutoTier] = useState<PerformanceTier>("high");
  const generationRef = useRef(0);
  const frameTimesRef = useRef<number[]>([]);
  const effectiveTier = options.tier ?? autoTier;

  useEffect(() => {
    scheduler.setReducedMotion(options.reducedMotion);
  }, [options.reducedMotion, scheduler]);

  useEffect(() => {
    scheduler.setTier(effectiveTier);
  }, [effectiveTier, scheduler]);

  useEffect(() => {
    if (options.interrupted) {
      generationRef.current = scheduler.interrupt();
      setFrame(scheduler.sample());
    }
  }, [options.interrupted, scheduler]);

  useEffect(() => {
    if (!options.plan) return;
    scheduler.loadFromPlan(options.plan, generationRef.current);
    setFrame(scheduler.sample(generationRef.current));
  }, [options.plan, scheduler]);

  useEffect(() => {
    scheduler.setJawEnergy(options.jawEnergy ?? 0, generationRef.current);
  }, [options.jawEnergy, scheduler]);

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      setFrame(scheduler.sample(generationRef.current));
      // Passive FPS probe for tier auto-degradation on weaker phones.
      if (options.tier === undefined) {
        const nowMs = performance.now();
        const times = frameTimesRef.current;
        times.push(nowMs);
        while (times.length > 0 && nowMs - times[0]! > FPS_SAMPLE_WINDOW_MS) {
          times.shift();
        }
        if (times.length > 1 && nowMs - times[0]! >= FPS_SAMPLE_WINDOW_MS) {
          const fps = ((times.length - 1) * 1000) / (nowMs - times[0]!);
          const floor = TIER_DOWNGRADE_FPS[effectiveTier];
          if (floor !== undefined && fps < floor) {
            setAutoTier(effectiveTier === "high" ? "medium" : "low");
            times.length = 0; // re-measure after the switch
          }
        }
      }
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scheduler, effectiveTier, options.tier]);

  return frame;
}
