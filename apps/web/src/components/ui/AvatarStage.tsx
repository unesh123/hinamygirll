import React, { Suspense, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Environment, ContactShadows, PerspectiveCamera } from "@react-three/drei";
import { VRMAvatar, type AvatarEmotion } from "./VRMAvatar";
import type { CompanionState } from "../../features/companion/types";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Maximize2, Minimize2 } from "lucide-react";
import { useProgress } from "@react-three/drei";

function LoadingOverlay() {
  const { active, progress } = useProgress();
  if (!active) return null;
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10,
        pointerEvents: "none",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
        <Loader2
          size={32}
          style={{ color: "#0891b2", animation: "spin 1s linear infinite" }}
        />
        <span style={{ fontSize: "0.82rem", color: "#64748b", fontWeight: 600 }}>
          HINAA awakening… {Math.round(progress)}%
        </span>
      </div>
    </div>
  );
}

/* ─── Map companion state to avatar emotion ────────────── */
function mapEmotion(state: CompanionState): AvatarEmotion {
  switch (state) {
    case "listening": return "playful";
    case "thinking": return "thinking";
    case "speaking": return "happy";
    case "interrupted": return "surprised";
    case "error": return "concerned";
    default: return "neutral";
  }
}

interface AvatarStageProps {
  state: CompanionState;
  jawEnergy?: React.MutableRefObject<number>;
  modelUrl?: string;
}

export function AvatarStage({ state, jawEnergy, modelUrl = "/models/hinaa.vrm" }: AvatarStageProps) {
  const [closeUp, setCloseUp] = useState(false);
  const isSpeaking = state === "speaking";
  const isListening = state === "listening";
  const isThinking = state === "thinking";
  const emotion = mapEmotion(state);

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none" }}>
      <LoadingOverlay />

      <Canvas
        shadows
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        <Suspense fallback={null}>
          <PerspectiveCamera
            makeDefault
            position={closeUp ? [0, 1.45, 0.85] : [0, 0.5, 2.2]}
            fov={closeUp ? 28 : 35}
          />

          {/* Lighting — soft cinematic */}
          <ambientLight intensity={1.3} color="#fffdf7" />
          <directionalLight position={[3, 4, 2]} intensity={1.6} color="#fffcf5" castShadow />
          <directionalLight position={[-2, -1, 2]} intensity={0.4} color="#e8f4ff" />

          {/* Mint + cyan rim lights */}
          <spotLight position={[4, 2.5, -4]} intensity={2.8} color="#0891b2" angle={0.4} penumbra={0.6} />
          <spotLight position={[-4, 2.5, -4]} intensity={2.8} color="#10b981" angle={0.4} penumbra={0.6} />

          {/* Pearl fill light */}
          <pointLight position={[0, 1, 3]} intensity={0.8} color="#fafbff" />

          <Environment preset="city" environmentIntensity={0.3} />

          <group position={[0, 0, 0]}>
            <VRMAvatar
              url={modelUrl}
              jawEnergy={jawEnergy}
              isSpeaking={isSpeaking}
              isListening={isListening}
              isThinking={isThinking}
              emotion={emotion}
              closeUp={closeUp}
            />
            <ContactShadows
              resolution={1024}
              scale={4}
              blur={2}
              opacity={0.35}
              far={1.8}
              position={[0, -1.2, 0]}
              color="#1e293b"
            />
          </group>
        </Suspense>
      </Canvas>

      {/* Close-up toggle button */}
      <motion.button
        type="button"
        onClick={(e) => { e.stopPropagation(); setCloseUp((v) => !v); }}
        style={{
          position: "absolute",
          bottom: 20,
          right: 20,
          zIndex: 5,
          pointerEvents: "all",
          width: 36,
          height: 36,
          borderRadius: 10,
          border: "1px solid rgba(255,255,255,0.65)",
          background: "rgba(255,255,255,0.6)",
          backdropFilter: "blur(12px)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          color: "#475569",
        }}
        whileHover={{ scale: 1.08, background: "rgba(255,255,255,0.85)" }}
        whileTap={{ scale: 0.92 }}
        title={closeUp ? "Full view" : "Close-up"}
        aria-label={closeUp ? "Show full avatar" : "Zoom to face"}
      >
        {closeUp ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
      </motion.button>

      {/* State aura behind avatar */}
      <AnimatePresence>
        {(state === "listening" || state === "thinking" || state === "speaking") && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: 400,
              height: 400,
              borderRadius: "50%",
              background:
                state === "listening"
                  ? "radial-gradient(circle, rgba(8,145,178,0.12) 0%, transparent 60%)"
                  : state === "thinking"
                    ? "radial-gradient(circle, rgba(124,58,237,0.08) 0%, transparent 60%)"
                    : "radial-gradient(circle, rgba(16,185,129,0.1) 0%, transparent 60%)",
              filter: "blur(40px)",
              zIndex: -1,
              pointerEvents: "none",
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

export default AvatarStage;
