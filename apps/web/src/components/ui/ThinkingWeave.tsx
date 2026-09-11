import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import styles from "./ThinkingWeave.module.css";

/**
 * ThinkingWeave — Hinaa's cognitive presence while a turn is composed.
 *
 * Three counter-rotating arcs (a "thought gyre") orbit a breathing core; a
 * travelling light sweeps the inner ring and the status line advances through
 * the actual stages of the turn. GSAP drives the animation on GPU transforms
 * and a single reduced-motion check keeps it calm when the OS asks for less.
 */

type Phase = "reading" | "reasoning" | "composing";

const PHRASES: Record<Phase, string> = {
  reading: "Reading your words",
  reasoning: "Weaving the answer",
  composing: "Polishing each line",
};

interface ThinkingWeaveProps {
  /** research = the gyre accelerates into a search sweep */
  mode?: "default" | "research";
  /** Live model-reasoning lines streamed by the backend this turn. */
  thoughts?: string[];
  /** Wall-clock thinking duration, ticking while live then frozen at first text. */
  durationMs?: number;
}

export function ThinkingWeave({ mode = "default", thoughts, durationMs }: ThinkingWeaveProps) {
  const [expanded, setExpanded] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLSpanElement>(null);
  const phaseRef = useRef<Phase>("reading");

  useEffect(() => {
    const root = rootRef.current;
    const label = labelRef.current;
    if (!root || !label) return;

    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const ctx = gsap.context(() => {
      if (reduceMotion) {
        label.textContent = PHRASES[mode === "research" ? "reasoning" : "reading"];
        return;
      }
      const spin = mode === "research" ? 2.6 : 4.2;
      gsap.to(root.querySelectorAll("[data-arc]"), {
        rotate: (index) => (index % 2 === 0 ? 360 : -360),
        duration: (index) => spin + index * 1.6,
        ease: "none",
        repeat: -1,
        transformOrigin: "50% 50%",
      });
      gsap.to(root.querySelectorAll("[data-node]"), {
        scale: 1.55,
        opacity: 1,
        duration: 0.72,
        ease: "sine.inOut",
        yoyo: true,
        repeat: -1,
        stagger: { each: 0.24, repeat: -1, yoyo: true },
      });
      gsap.to(root.querySelector("[data-core]"), {
        scale: 1.14,
        opacity: 0.95,
        duration: 1.05,
        ease: "power1.inOut",
        yoyo: true,
        repeat: -1,
      });
      gsap.fromTo(
        root.querySelector("[data-sweep]"),
        { strokeDashoffset: 0 },
        {
          strokeDashoffset: -132,
          duration: mode === "research" ? 0.9 : 1.5,
          ease: "none",
          repeat: -1,
        },
      );

      // Stage narration: reading → reasoning → composing, on a soft loop.
      const phases: Phase[] = mode === "research"
        ? ["reading", "reasoning", "reasoning", "composing"]
        : ["reading", "reasoning", "composing"];
      let step = 0;
      const tl = gsap.timeline({ repeat: -1, repeatDelay: 0 });
      const cycle = () => {
        const next = phases[step % phases.length];
        step += 1;
        if (next === phaseRef.current) return;
        phaseRef.current = next;
        tl.to(label, {
          opacity: 0,
          y: -4,
          duration: 0.22,
          ease: "power2.in",
          onComplete: () => {
            label.textContent = `${PHRASES[next]}…`;
            gsap.fromTo(label, { opacity: 0, y: 5 }, { opacity: 1, y: 0, duration: 0.3, ease: "power2.out" });
          },
        });
      };
      cycle();
      gsap.delayedCall(0, cycle);
      const ticker = gsap.delayedCall(2.4, function repeat() {
        cycle();
        ticker.restart(true);
      });
    }, root);

    return () => ctx.revert();
  }, [mode]);

  return (
    <div ref={rootRef} className={styles.weave} role="status" aria-live="polite">
      <svg width="46" height="46" viewBox="0 0 46 46" aria-hidden="true" className={styles.gyre}>
        <defs>
          <linearGradient id="tw-rose" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#ffdfaa" />
            <stop offset="55%" stopColor="#ffb1c6" />
            <stop offset="100%" stopColor="#ee91ad" />
          </linearGradient>
          <linearGradient id="tw-violet" x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#b18cff" />
            <stop offset="100%" stopColor="#ee91ad" stopOpacity="0.2" />
          </linearGradient>
          <linearGradient id="tw-ice" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0%" stopColor="#7fd4ff" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#7fd4ff" stopOpacity="0.1" />
          </linearGradient>
        </defs>
        <g data-arc>
          <circle
            cx="23" cy="23" r="19.5" fill="none"
            stroke="url(#tw-rose)" strokeWidth="1.6" strokeLinecap="round"
            strokeDasharray="62 60" opacity="0.9"
          />
        </g>
        <g data-arc>
          <circle
            cx="23" cy="23" r="14.5" fill="none"
            stroke="url(#tw-violet)" strokeWidth="1.4" strokeLinecap="round"
            strokeDasharray="38 53" opacity="0.85"
          />
        </g>
        <g data-arc>
          <circle
            cx="23" cy="23" r="9.6" fill="none"
            stroke="url(#tw-ice)" strokeWidth="1.2" strokeLinecap="round"
            strokeDasharray="14 46.5" opacity="0.8"
          />
        </g>
        <circle data-sweep cx="23" cy="23" r="21" fill="none" stroke="#ffdfaa" strokeWidth="1.1" strokeLinecap="round" strokeDasharray="6 126" opacity="0.85" />
        <circle data-node cx="42.5" cy="23" r="1.8" fill="#ffd6e1" opacity="0.55" />
        <circle data-node cx="23" cy="8.5" r="1.6" fill="#cdb6ff" opacity="0.55" />
        <circle data-node cx="6.5" cy="23" r="1.4" fill="#9fe3ff" opacity="0.55" />
        <g data-core>
          <circle cx="23" cy="23" r="4.2" fill="url(#tw-rose)" opacity="0.8" />
          <circle cx="23" cy="23" r="1.9" fill="#fff3f7" />
        </g>
      </svg>
      <span className={styles.label} ref={labelRef}>{PHRASES.reading}…</span>
          {thoughts && thoughts.length > 0 && (
        <div className={styles.thoughts}>
          <p className={styles.thoughtLatest} key={thoughts.length}>
            {thoughts[thoughts.length - 1]}
          </p>
          <div className={styles.thoughtMeta}>
            {durationMs != null && durationMs > 0 && (
              <span className={styles.thoughtTime}>{(durationMs / 1000).toFixed(1)}s</span>
            )}
            {thoughts.length > 1 && (
              <button
                type="button"
                className={styles.thoughtToggle}
                onClick={() => setExpanded((v) => !v)}
                aria-expanded={expanded}
              >
                {expanded ? "hide the weave" : `watch the weave (${thoughts.length})`}
              </button>
            )}
          </div>
          {expanded && (
            <ol className={styles.thoughtChain}>
              {thoughts.map((thought, index) => (
                <li key={`${index}-${thought.slice(0, 24)}`}>{thought}</li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}

export default ThinkingWeave;
