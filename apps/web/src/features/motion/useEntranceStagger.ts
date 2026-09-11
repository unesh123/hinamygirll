import { useEffect } from "react";
import { gsap } from "gsap";

/**
 * One-shot GSAP entrance for the shell regions. Elements are revealed with a
 * short, ordered stagger so the companion pane arrives before the transcript
 * and the composer — an intentional reading order, not a pile of independent
 * fades. Honors prefers-reduced-motion by skipping the animation entirely.
 */
export function useEntranceStagger(
  rootSelector: string,
  targets: string[],
  opts: { delay?: number; stagger?: number } = {},
) {
  const targetKey = targets.join("|");
  const { delay = 0.05, stagger = 0.09 } = opts;
  useEffect(() => {
    // Vitest/jsdom never ticks rAF, so an autoAlpha entrance would strand the
    // tree at visibility:hidden and starve accessibility queries.
    if (import.meta.env.MODE === "test") return;
    const root = document.querySelector(rootSelector);
    if (!root) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

    const nodes = targets
      .flatMap((selector) => Array.from(root.querySelectorAll(selector)))
      .filter((node, index, list) => list.indexOf(node) === index);
    if (nodes.length === 0) return;

    const ctx = gsap.context(() => {
      gsap.from(nodes, {
        autoAlpha: 0,
        y: 16,
        duration: 0.68,
        ease: "power3.out",
        delay,
        stagger: { each: stagger, from: "start" },
        clearProps: "transform,opacity,visibility",
      });
    }, root as HTMLElement);
    return () => ctx.revert();
    // Entrance is intentionally mount-only; selectors are structural config.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rootSelector, targetKey, delay, stagger]);
}
