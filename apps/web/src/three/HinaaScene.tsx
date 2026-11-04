import React, { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  OrbitControls,
  PerspectiveCamera,
} from "@react-three/drei";
import { VRMAvatar } from "../components/ui/VRMAvatar";
import type { CompanionState } from "../features/companion/types";

export interface HinaaSceneProps {
  modelUrl?: string;
  companionState?: CompanionState;
  isWalking?: boolean;
  speakingRef?: React.MutableRefObject<boolean>;
  jawEnergy?: React.MutableRefObject<number>;
  autoRotateSpeed?: number;
}

export function HinaaSceneContent({
  modelUrl = "/models/hinaa-original.vrm",
  companionState = "idle",
  isWalking = false,
  speakingRef,
  jawEnergy,
  autoRotateSpeed = 0.6,
}: HinaaSceneProps) {
  return (
    <>
      {/* Background Fog matching Canvas #0b0710 */}
      <fog attach="fog" args={["#0b0710", 3, 12]} />

      <PerspectiveCamera makeDefault position={[0, 0.4, 2.2]} fov={38} />

      {/* ── Three-Point Studio Lighting ── */}
      {/* 1. Ambient fill */}
      <ambientLight intensity={0.6} />

      {/* 2. Key directional light with shadow */}
      <directionalLight
        position={[2.5, 4.0, 3.0]}
        intensity={1.2}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-near={0.5}
        shadow-camera-far={10}
        shadow-camera-left={-2}
        shadow-camera-right={2}
        shadow-camera-top={2}
        shadow-camera-bottom={-2}
      />

      {/* 3. Rim light with cool blue tint */}
      <directionalLight
        position={[-3.0, 2.5, -2.5]}
        intensity={0.8}
        color="#a5c9ff"
      />

      {/* HDRI Environment Reflections */}
      <Environment preset="city" />

      {/* Ground Contact Shadows */}
      <ContactShadows
        position={[0, -0.95, 0]}
        opacity={0.65}
        scale={3.5}
        blur={2.0}
        far={1.6}
      />

      {/* Clamped Orbit Controls (No zoom, no pan, clamped polar angles, auto-rotation) */}
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        minPolarAngle={Math.PI / 3.5}
        maxPolarAngle={Math.PI / 1.8}
        autoRotate
        autoRotateSpeed={autoRotateSpeed}
      />

      {/* VRM Avatar Actor */}
      <group position={[0, -0.92, 0]}>
        <VRMAvatar
          modelUrl={modelUrl}
          companionState={companionState}
          isWalking={isWalking}
          speakingRef={speakingRef}
          jawEnergy={jawEnergy}
        />
      </group>
    </>
  );
}

export function HinaaScene(props: HinaaSceneProps) {
  return (
    <Canvas
      shadows
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      style={{
        width: "100%",
        height: "100%",
        background: "radial-gradient(circle at 50% 30%, #171124 0%, #0b0710 100%)",
      }}
    >
      <HinaaSceneContent {...props} />
    </Canvas>
  );
}
