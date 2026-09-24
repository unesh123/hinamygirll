import { motion } from "framer-motion";
import type { CompanionState } from "../../features/companion/types";

const stateAura: Record<CompanionState, { color: string; opacity: number }> = {
  idle:          { color: "#ffffff",  opacity: 0.03 },
  listening:     { color: "#c4b5fd",  opacity: 0.15 },
  understanding: { color: "#a5f3fc",  opacity: 0.12 },
  thinking:      { color: "#a5f3fc",  opacity: 0.12 },
  researching:   { color: "#93c5fd",  opacity: 0.14 },
  using_tool:    { color: "#fed7aa",  opacity: 0.12 },
  generating:    { color: "#f472b6",  opacity: 0.14 },
  writing:       { color: "#c084fc",  opacity: 0.12 },
  waiting:       { color: "#e2e8f0",  opacity: 0.08 },
  speaking:      { color: "#a7f3d0",  opacity: 0.14 },
  success:       { color: "#86efac",  opacity: 0.15 },
  confused:      { color: "#fef08a",  opacity: 0.12 },
  interrupted:   { color: "#fef3c7",  opacity: 0.10 },
  error:         { color: "#fca5a5",  opacity: 0.10 },
};

interface FullScreenAuraProps { state: CompanionState; }

export function FullScreenAura({ state }: FullScreenAuraProps) {
  const a = stateAura[state];
  return (
    <div className="fullscreen-aura" aria-hidden="true" style={{ position: "fixed", inset: 0, zIndex: 0, pointerEvents: "none", overflow: "hidden" }}>
      {(["tl", "tr", "bl", "br"] as const).map((c) => (
        <motion.div
          key={`${c}-${state}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: a.opacity }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          style={{
            position: "absolute",
            width: "60vmax", height: "60vmax",
            [c[0] === "t" ? "top" : "bottom"]: "-20%",
            [c[1] === "l" ? "left" : "right"]: "-20%",
            background: `radial-gradient(circle at ${c[1] === "l" ? 0 : 100}% ${c[0] === "t" ? 0 : 100}%, ${a.color} 0%, transparent 60%)`,
            filter: "blur(60px)",
            borderRadius: "50%",
          }}
        />
      ))}
    </div>
  );
}
