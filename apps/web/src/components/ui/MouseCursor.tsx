import { useEffect, useRef } from "react";

interface MouseCursorProps {}

export function MouseCursor(_props: MouseCursorProps) {
  const cursorRef = useRef<HTMLDivElement>(null);
  const trailRef = useRef<HTMLDivElement[]>([]);
  const pos = useRef({ x: 0, y: 0 });
  const trailPositions = useRef<Array<{ x: number; y: number }>>([]);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const TRAIL_LENGTH = 8;

    // Initialize trail positions
    trailPositions.current = Array.from({ length: TRAIL_LENGTH }, () => ({ x: 0, y: 0 }));

    const onMouseMove = (e: MouseEvent) => {
      pos.current = { x: e.clientX, y: e.clientY };
    };

    const animate = () => {
      // Move main cursor
      if (cursorRef.current) {
        cursorRef.current.style.transform = `translate(${pos.current.x - 8}px, ${pos.current.y - 8}px)`;
      }

      // Update trail
      trailPositions.current.unshift({ ...pos.current });
      if (trailPositions.current.length > TRAIL_LENGTH) {
        trailPositions.current = trailPositions.current.slice(0, TRAIL_LENGTH);
      }

      trailRef.current.forEach((el, i) => {
        const tp = trailPositions.current[i];
        if (el && tp) {
          const size = 6 - i * 0.5;
          const opacity = 0.4 - i * 0.04;
          el.style.transform = `translate(${tp.x - size / 2}px, ${tp.y - size / 2}px)`;
          el.style.width = `${size}px`;
          el.style.height = `${size}px`;
          el.style.opacity = `${Math.max(0, opacity)}`;
        }
      });

      rafRef.current = requestAnimationFrame(animate);
    };

    document.addEventListener("mousemove", onMouseMove);
    rafRef.current = requestAnimationFrame(animate);

    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <>
      {/* Main cursor dot */}
      <div ref={cursorRef} className="custom-cursor" aria-hidden="true" />
      {/* Trail particles */}
      {Array.from({ length: 8 }, (_, i) => (
        <div
          key={i}
          ref={(el) => {
            if (el) trailRef.current[i] = el;
          }}
          className="custom-cursor-trail"
          aria-hidden="true"
          style={{ animationDelay: `${i * 0.05}s` }}
        />
      ))}
    </>
  );
}
