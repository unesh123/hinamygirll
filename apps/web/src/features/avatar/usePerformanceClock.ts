import { useEffect, useMemo, useRef, useState } from "react";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import {
  PerformanceScheduler,
  type ActivePerformanceFrame,
} from "./performanceScheduler";

export function usePerformanceClock(options: {
  plan?: AssistantTurnPlan;
  jawEnergy?: number;
  reducedMotion: boolean;
  interrupted: boolean;
}) {
  const scheduler = useMemo(() => new PerformanceScheduler(), []);
  const [frame, setFrame] = useState<ActivePerformanceFrame>(() =>
    scheduler.sample(),
  );
  const generationRef = useRef(0);

  useEffect(() => {
    scheduler.setReducedMotion(options.reducedMotion);
  }, [options.reducedMotion, scheduler]);

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
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(raf);
  }, [scheduler]);

  return frame;
}
