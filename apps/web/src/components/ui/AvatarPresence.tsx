/**
 * AvatarPresence — Centered avatar viewport with relaxed pose.
 * Head stays stable (no spinning). Arms down. Fast & smooth.
 */

import type * as React from "react";
import { Suspense, useState, useRef, useEffect, useCallback } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows } from "@react-three/drei";
import { motion } from "framer-motion";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRM, VRMUtils, VRMExpressionPresetName } from "@pixiv/three-vrm";
import * as THREE from "three";
import { Maximize2 } from "lucide-react";
import type { CompanionState } from "../../features/companion/types";

export type PresenceMode = "closeup" | "portrait" | "full" | "hidden";

/* ─── Relaxed idle: arms down, elbows bent ────────────── */
/*
 * Angles are for three-vrm NORMALIZED bones (T-pose baseline, model facing
 * +Z). The left arm extends +X, so a NEGATIVE Z rotation lowers it toward
 * the body; the right arm mirrors with a positive Z rotation. (The previous
 * signs were inverted, which raised both hands to the face.)
 */
const RELAXED_IDLE: Record<string, [number, number, number]> = {
  leftUpperArm:  [0.05, 0, -1.15],
  leftLowerArm:  [0, 0, -0.25],
  leftHand:      [0, 0, -0.08],
  rightUpperArm: [0.05, 0, 1.15],
  rightLowerArm: [0, 0, 0.25],
  rightHand:     [0, 0, 0.08],
};

/* ─── Measured model anchors (Phase 15: no magic camera numbers) ── */
export interface ModelAnchors {
  /** World Y of the eye midpoint (falls back to 92% of height). */
  eyeY: number;
  /** World Y of the chest anchor. */
  chestY: number;
  /** Model bounding-box height (after grounding at y=0). */
  height: number;
  /** Bounding-box vertical center. */
  centerY: number;
}

/** Camera framing derived from the measured skeleton, per presence mode. */
function cameraForMode(mode: PresenceMode, a: ModelAnchors): { pos: [number, number, number]; target: [number, number, number]; fov: number } {
  switch (mode) {
    case "closeup": {
      // Head and shoulders: look at the eyes from just below eye level.
      const t = a.eyeY - a.height * 0.02;
      return { pos: [0, t, a.height * 0.42], target: [0, t, 0], fov: 24 };
    }
    case "full": {
      // Whole body in frame with a little breathing room.
      const fov = 32;
      const dist = (a.height * 0.62) / Math.tan((fov * Math.PI) / 360);
      return { pos: [0, a.centerY, dist * 0.55], target: [0, a.centerY, 0], fov };
    }
    case "portrait":
    default: {
      // Chest-up portrait: eyes in the upper third, chest at the bottom.
      const t = (a.eyeY + a.chestY) / 2;
      return { pos: [0, t, a.height * 0.78], target: [0, t, 0], fov: 28 };
    }
  }
}

const DEFAULT_ANCHORS: ModelAnchors = { eyeY: 1.45, chestY: 1.15, height: 1.6, centerY: 0.8 };

/* ─── VRM Model ────────────────────────────────────────── */
function Model({
  url, state, isSpeaking, jawEnergy, onLoadFailed, onAnchors,
}: {
  url: string; state: CompanionState; isSpeaking: boolean;
  jawEnergy?: React.MutableRefObject<number>;
  onLoadFailed?: () => void;
  onAnchors?: (a: ModelAnchors) => void;
}) {
  const vrmRef = useRef<VRM | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const timeRef = useRef(0);
  const blinkRef = useRef(2 + Math.random() * 3);
  const mouthRef = useRef(0);

  useEffect(() => {
    let ok = true;
    setFailed(false);
    const ldr = new GLTFLoader();
    ldr.crossOrigin = "anonymous";
    ldr.register(p => new VRMLoaderPlugin(p));

    // Fallback chain: requested model → committed backup model. The main
    // `hinaa.vrm` slot is a gitignored drop-in slot for the user's own VRoid
    // export, so fresh clones only ship `hinaa.vrm.bak` (MIT licensed).
    const candidates = url.endsWith("/hinaa.vrm") ? [url, `${url}.bak`] : [url];

    const tryLoad = (index: number) => {
      if (!ok) return;
      if (index >= candidates.length) {
        setFailed(true);
        onLoadFailed?.();
        return;
      }
      ldr.load(candidates[index], gltf => {
        if (!ok) return;
        const v = gltf.userData.vrm as VRM;
        if (!v) { tryLoad(index + 1); return; }
        v.scene.traverse((o: THREE.Object3D) => {
          o.frustumCulled = false;
          if ((o as THREE.Mesh).isMesh) ((o as THREE.Mesh).material as THREE.Material).side = THREE.DoubleSide;
        });
        // Face the camera: VRM 0.x models load facing -Z; rotateVRM0 turns
        // them to the VRM 1.0 convention (+Z, toward our camera). VRM 1.0
        // models are untouched. Never hard-code a 180° flip here.
        VRMUtils.rotateVRM0(v);

        // Ground the feet at y=0 and measure real anchors from the skeleton.
        v.scene.updateMatrixWorld(true);
        const box = new THREE.Box3().setFromObject(v.scene);
        v.scene.position.y -= box.min.y;
        v.scene.updateMatrixWorld(true);
        const grounded = new THREE.Box3().setFromObject(v.scene);
        const height = grounded.max.y - grounded.min.y;
        const centerY = (grounded.max.y + grounded.min.y) / 2;
        const worldY = (bone: string): number | null => {
          const node = v.humanoid?.getNormalizedBoneNode(bone as Parameters<NonNullable<VRM["humanoid"]>["getNormalizedBoneNode"]>[0]);
          if (!node) return null;
          const pos = new THREE.Vector3();
          node.getWorldPosition(pos);
          return pos.y;
        };
        const headY = worldY("head");
        const eyeY = worldY("leftEye") ?? (headY !== null ? headY + height * 0.035 : height * 0.92);
        const chestY = worldY("upperChest") ?? worldY("chest") ?? height * 0.72;
        onAnchors?.({ eyeY, chestY, height, centerY });

        vrmRef.current = v;
        setLoaded(true);
      }, undefined, () => { if (ok) tryLoad(index + 1); });
    };
    tryLoad(0);
    return () => { ok = false; };
  }, [url, onLoadFailed, onAnchors]);

  useFrame((_, dt) => {
    const vrm = vrmRef.current;
    if (!vrm) return;
    const d = Math.min(dt, 0.1);
    timeRef.current += d;
    const t = timeRef.current;
    const hd = vrm.humanoid;
    const em = vrm.expressionManager;

    if (!hd || !em) { vrm.update(d); return; }

    // ── Lip sync ──────────────────────────────────────
    let tm = 0;
    if (isSpeaking && jawEnergy) tm = Math.min(0.9, jawEnergy.current * 1.2);
    mouthRef.current += (tm - mouthRef.current) * d * 16;
    try { em.setValue(VRMExpressionPresetName.Aa, mouthRef.current); } catch {}

    // ── Blink ──────────────────────────────────────────
    blinkRef.current -= d;
    let bv = 0;
    if (blinkRef.current <= 0) {
      if (blinkRef.current < -0.12) blinkRef.current = 2 + Math.random() * 4;
      else bv = Math.sin(Math.max(0, Math.min(1, (blinkRef.current + 0.12) / 0.12)) * Math.PI);
    }
    try { em.setValue(VRMExpressionPresetName.Blink, bv); } catch {}

    // ── Subtle emotion ─────────────────────────────────
    try {
      if (state === "speaking") em.setValue(VRMExpressionPresetName.Happy, 0.1);
      else if (state === "error") em.setValue(VRMExpressionPresetName.Sad, 0.08);
    } catch {}

    vrm.update(d);

    // ── Apply relaxed idle AFTER update (prevents T-pose) ──
    // Use SET not ADD — prevents accumulation/spinning
    // Normalized bones are rest-pose relative (T-pose baseline), so the same
    // angles produce the same relaxed pose on ANY humanoid VRM. Raw bones
    // bake each model's own rest pose and gave lifted "doll hands" on some
    // assets — only use them if the normalized rig is missing.
    for (const [bn, r] of Object.entries(RELAXED_IDLE)) {
      const bone = hd.getNormalizedBoneNode(bn as any) ?? (hd as any).getRawBoneNode?.(bn) as THREE.Bone | null;
      if (bone) bone.rotation.set(r[0], r[1], r[2]);
    }

    // ── Breathing: chest only, SET not ADD ─────────────
    const chest = hd.getNormalizedBoneNode("chest" as any);
    if (chest) chest.rotation.x = Math.sin(t * 1.4) * 0.005;

    // ── Head: SET absolute value, no accumulation ──────
    const head = hd.getNormalizedBoneNode("head");
    if (head) {
      head.rotation.set(
        Math.sin(t * 0.4) * 0.01,  // tiny pitch
        Math.sin(t * 0.25) * 0.02, // tiny yaw — SET, not +=
        Math.sin(t * 0.35) * 0.005 // tiny roll
      );
    }
  });

  if (failed) return null;
  if (!loaded) return null;
  return <primitive object={vrmRef.current!.scene} />;
}

/* ─── Camera ───────────────────────────────────────────── */
function Cam({ mode, anchors }: { mode: PresenceMode; anchors: ModelAnchors }) {
  const cfg = cameraForMode(mode, anchors);
  const c = useThree(s => s.camera);
  const pRef = useRef(new THREE.Vector3(...cfg.pos));
  const tRef = useRef(new THREE.Vector3(...cfg.target));
  const fovRef = useRef(cfg.fov);
  const snappedRef = useRef(false);

  useEffect(() => {
    pRef.current.set(...cfg.pos);
    tRef.current.set(...cfg.target);
    fovRef.current = cfg.fov;
    // First real measurement: snap instead of a long lerp from nowhere.
    if (!snappedRef.current) {
      c.position.copy(pRef.current);
      c.lookAt(tRef.current);
      snappedRef.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, anchors, c]);

  useFrame((_, dt) => {
    const smooth = 1 - Math.exp(-Math.min(dt, 0.1) * 4);
    c.position.lerp(pRef.current, smooth);
    c.lookAt(tRef.current);
    if (c instanceof THREE.PerspectiveCamera) {
      c.fov += (fovRef.current - c.fov) * smooth;
      c.updateProjectionMatrix();
    }
  });
  return null;
}

/* ─── Fallback ──────────────────────────────────────────── */
function AvatarFallback({ state, failed = false }: { state: CompanionState; failed?: boolean }) {
  return (
    <div style={{
      width: "100%", height: "100%", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 16,
      color: "#64748b", fontSize: "0.85rem", textAlign: "center", padding: 24,
    }}>
      <div style={{
        width: 80, height: 80, borderRadius: "50%",
        background: "linear-gradient(135deg, rgba(167,243,208,0.5), rgba(103,232,249,0.5))",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "2rem", border: "2px solid rgba(255,255,255,0.8)",
        boxShadow: "0 4px 20px rgba(16,185,129,0.2)",
      }}>◇</div>
      <div>
        <div style={{ fontWeight: 700, color: "#1a1f2e" }}>HINAA</div>
        <div style={{ fontSize: "0.72rem", marginTop: 4 }}>
          {state === "idle" ? "Ready" : state === "listening" ? "Listening…" :
           state === "speaking" ? "Speaking…" : state === "thinking" ? "Thinking…" : "Present"}
        </div>
        {failed && (
          <div style={{ fontSize: "0.68rem", marginTop: 8, color: "#94a3b8", maxWidth: 220 }}>
            3D model unavailable — place a VRoid export at
            {" "}<code>public/models/hinaa.vrm</code> and restart the dev server.
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Main ─────────────────────────────────────────────── */
interface Props {
  mode: PresenceMode;
  state: CompanionState;
  jawEnergy?: React.MutableRefObject<number>;
  modelUrl?: string;
  onModeChange?: (m: PresenceMode) => void;
}

export function AvatarPresence({
  mode, state, jawEnergy,
  modelUrl = "/models/hinaa.vrm",
  onModeChange,
}: Props) {
  const [webglFailed, setWebglFailed] = useState(false);
  const [modelFailed, setModelFailed] = useState(false);
  const [anchors, setAnchors] = useState<ModelAnchors>(DEFAULT_ANCHORS);
  const handleLoadFailed = useCallback(() => setModelFailed(true), []);
  const handleAnchors = useCallback((a: ModelAnchors) => setAnchors(a), []);

  if (mode === "hidden") return null;

  const showFallback = webglFailed || modelFailed;

  const cycle = () => {
    const modes: PresenceMode[] = ["closeup", "portrait", "full"];
    const idx = modes.indexOf(mode);
    onModeChange?.(modes[(idx + 1) % modes.length]);
  };

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", minHeight: 180 }}>
      {/* Soft halo */}
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse 60% 60% at 50% 40%, rgba(103,232,249,0.06) 0%, transparent 70%)", pointerEvents: "none", zIndex: 0 }} />

      {!showFallback && (
        <Canvas
          style={{ position: "absolute", inset: 0, zIndex: 1 }}
          dpr={[1, 1.5]}
          gl={{ antialias: true, alpha: true, preserveDrawingBuffer: false, powerPreference: "default", failIfMajorPerformanceCaveat: false }}
          onCreated={({ gl }) => {
            gl.domElement.addEventListener("webglcontextlost", (e) => { e.preventDefault(); setWebglFailed(true); }, { once: true });
          }}
        >
          <Suspense fallback={null}>
            <Cam mode={mode} anchors={anchors} />
            <ambientLight intensity={1.0} color="#fffdf7" />
            <directionalLight position={[2, 3, 2]} intensity={1.2} color="#fffcf5" />
            <spotLight position={[-3, 1.5, 2]} intensity={1.5} color="#a7f3d0" angle={0.6} penumbra={0.5} />
            <spotLight position={[3, 1.5, -1]} intensity={1.2} color="#c4b5fd" angle={0.5} penumbra={0.5} />
            <pointLight position={[0, 1.2, 2]} intensity={0.5} color="#fff8f0" />
            <Model url={modelUrl} state={state} isSpeaking={state === "speaking"} jawEnergy={jawEnergy} onLoadFailed={handleLoadFailed} onAnchors={handleAnchors} />
            <ContactShadows resolution={256} scale={3} blur={2} opacity={0.22} far={1.5} position={[0, 0.01, 0]} color="#1e293b" />
          </Suspense>
        </Canvas>
      )}
      {showFallback && <AvatarFallback state={state} failed={modelFailed} />}

      {/* Mode toggle */}
      <div style={{ position: "absolute", bottom: 8, right: 8, zIndex: 5 }}>
        <motion.button type="button" onClick={cycle} whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.92 }}
          style={{ width: 28, height: 28, borderRadius: 8, border: "1px solid rgba(255,255,255,0.6)", background: "rgba(255,255,255,0.55)", backdropFilter: "blur(8px)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b" }}
          title={`View: ${mode}`}>
          <Maximize2 size={12} />
        </motion.button>
      </div>
    </div>
  );
}

export default AvatarPresence;
