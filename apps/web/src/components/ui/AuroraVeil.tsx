import { useEffect, useRef } from "react";
import type { CompanionState } from "../../features/companion/types";

/**
 * AuroraVeil — the ambient depth layer of the HINAA workspace.
 *
 * Paints drifting aurora blobs, a faint spatial mesh, a top light beam and
 * film grain behind every surface. It also feeds a pointer-following
 * spotlight into CSS custom properties (--veil-x / --veil-y) that panels,
 * the composer and the avatar stage pick up for edge lighting, and drives
 * the legacy #hinaa-cursor-dot so the cursor reads as a living glow.
 *
 * The veil tints itself from the companion state: idle glows rose,
 * listening shifts to ice, thinking to violet, speaking to mint — mirroring
 * Hinaa's own presence without adding a second animation surface.
 *
 * Decorative only: never steals pointer events, suspends all motion for
 * prefers-reduced-motion users and skips the pointer layer on touch devices.
 */

interface AuroraVeilProps {
  state?: CompanionState;
}

const VEIL_SMOOTHING = 0.14;
const IDLE_DIM_AFTER_MS = 4200;

export function AuroraVeil({ state = "idle" }: AuroraVeilProps) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const finePointer = window.matchMedia?.("(pointer: fine)").matches ?? false;
    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

    const target = { x: window.innerWidth / 2, y: window.innerHeight * 0.4 };
    const current = { ...target };
    let raf = 0;
    let idleTimer = 0;
    let hotElement = false;
    const dot = document.getElementById("hinaa-cursor-dot");

    const paint = () => {
      current.x += (target.x - current.x) * VEIL_SMOOTHING;
      current.y += (target.y - current.y) * VEIL_SMOOTHING;
      const host = document.documentElement;
      host.style.setProperty("--veil-x", `${current.x.toFixed(1)}px`);
      host.style.setProperty("--veil-y", `${current.y.toFixed(1)}px`);
      if (dot) {
        dot.style.transform = `translate(${current.x.toFixed(1)}px, ${current.y.toFixed(1)}px) translate(-50%, -50%) scale(${hotElement ? 2.35 : 1})`;
      }
      raf = window.requestAnimationFrame(paint);
    };

    if (!finePointer || reducedMotion) return;

    const onPointerMove = (event: PointerEvent) => {
      target.x = event.clientX;
      target.y = event.clientY;
      if (rootRef.current) rootRef.current.classList.remove("veil-idle");
      window.clearTimeout(idleTimer);
      idleTimer = window.setTimeout(() => rootRef.current?.classList.add("veil-idle"), IDLE_DIM_AFTER_MS);
    };

    const setHot = (event: PointerEvent) => {
      const interactive = (event.target as HTMLElement | null)?.closest?.(
        'button, a, input, textarea, select, [role="button"], summary, [data-veil-hot]',
      );
      hotElement = Boolean(interactive);
      dot?.classList.toggle("veil-hot", hotElement);
    };

    const onPointerOver = (event: PointerEvent) => setHot(event);
    const onPointerOut = (event: PointerEvent) => setHot(event);

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("pointerover", onPointerOver, { passive: true });
    document.addEventListener("pointerout", onPointerOut, { passive: true });
    raf = window.requestAnimationFrame(paint);

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerover", onPointerOver);
      document.removeEventListener("pointerout", onPointerOut);
      window.cancelAnimationFrame(raf);
      window.clearTimeout(idleTimer);
    };
  }, []);

  return (
    <div
      ref={rootRef}
      className="hinaa-veil"
      data-veil-state={state}
      aria-hidden="true"
    >
      <div className="hinaa-veil-aurora">
        <i className="hinaa-veil-blob hinaa-veil-blob--a" />
        <i className="hinaa-veil-blob hinaa-veil-blob--b" />
        <i className="hinaa-veil-blob hinaa-veil-blob--c" />
        <i className="hinaa-veil-blob hinaa-veil-blob--d" />
      </div>
      <div className="hinaa-veil-mesh" />
      <div className="hinaa-veil-beam" />
      <div className="hinaa-veil-spot" />
      <div className="hinaa-veil-grain" />
    </div>
  );
}

export default AuroraVeil;
