import React, { useEffect, useRef } from "react";

export interface VoiceWaveBarsProps {
  active?: boolean;
  energyRef?: React.MutableRefObject<number>;
  compact?: boolean;
}

const RESTING_HEIGHTS = [0.22, 0.36, 0.48, 0.36, 0.22];
const PHASE_OFFSETS = [0.0, 0.75, 1.5, 2.25, 3.0];

/**
 * 5-bar real-time voice amplitude waveform (violet -> cyan gradient).
 */
export const VoiceWaveBars: React.FC<VoiceWaveBarsProps> = ({
  active = false,
  energyRef,
  compact = false,
}) => {
  const barRefs = useRef<Array<HTMLSpanElement | null>>([]);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!active) {
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      barRefs.current.forEach((bar, i) => {
        if (bar) {
          bar.style.transform = `scaleY(${RESTING_HEIGHTS[i]})`;
          bar.style.opacity = "0.55";
        }
      });
      return;
    }

    let running = true;
    const started = performance.now();
    const tick = (now: number) => {
      if (!running) return;
      const elapsed = (now - started) / 1000;
      const liveEnergy = Math.max(0.25, Math.min(1, (energyRef?.current ?? 0) * 1.8 + 0.35));
      barRefs.current.forEach((bar, i) => {
        if (!bar) return;
        const wave = 0.45 + 0.55 * Math.abs(Math.sin(elapsed * 7.2 + PHASE_OFFSETS[i]));
        const scale = Math.max(0.2, Math.min(1.0, wave * liveEnergy));
        bar.style.transform = `scaleY(${scale.toFixed(3)})`;
        bar.style.opacity = "1";
      });
      rafRef.current = window.requestAnimationFrame(tick);
    };
    rafRef.current = window.requestAnimationFrame(tick);

    return () => {
      running = false;
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [active, energyRef]);

  const height = compact ? 16 : 22;
  const barWidth = compact ? 2.5 : 3;

  return (
    <span
      className="hinaa-voice-wave-bars"
      data-testid="voice-wave-bars"
      data-active={active ? "true" : "false"}
      aria-hidden="true"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: compact ? 2 : 3,
        height,
        paddingInline: 2,
      }}
    >
      {RESTING_HEIGHTS.map((rest, idx) => (
        <span
          key={idx}
          ref={(el) => {
            barRefs.current[idx] = el;
          }}
          style={{
            display: "block",
            width: barWidth,
            height,
            borderRadius: 999,
            background: "linear-gradient(180deg, #06b6d4 0%, #8b5cf6 100%)",
            boxShadow: active ? "0 0 8px rgba(139, 92, 246, 0.55)" : "none",
            transformOrigin: "center bottom",
            transform: `scaleY(${rest})`,
            opacity: active ? 1 : 0.55,
            transition: active ? "opacity 160ms ease" : "transform 220ms ease, opacity 220ms ease",
          }}
        />
      ))}
    </span>
  );
};
