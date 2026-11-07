import type { RenderQuality } from "./face/renderQuality";

interface RigProps {
  quality: RenderQuality;
  /** Realistic rigs run a stronger warm key; toon rigs get a gentle rim only. */
  realistic?: boolean;
  /** Only the back rim lights, for toon rigs that already have their own key/fill. */
  rimOnly?: boolean;
}

/** Key / fill / rim rig: warm key (soft shadows when the device allows), cool fill, and back rims for hair and skin edges. */
export function HumanLightingRig({ quality, realistic = true, rimOnly = false }: RigProps) {
  const size = quality.shadowMapSize;
  if (rimOnly) {
    return (
      <>
        <directionalLight position={[-0.8, 2.2, -2.6]} intensity={0.55} color="#ffd9e6" />
        <directionalLight position={[1.4, 1.6, -2.2]} intensity={0.3} color="#d6e4ff" />
      </>
    );
  }
  return (
    <>
      <hemisphereLight args={["#fff4ea", "#8d7f9a", realistic ? 0.35 : 0.3]} />
      <directionalLight
        position={[1.6, 2.8, 2.4]}
        intensity={realistic ? 2.2 : 0.9}
        color="#fff1e0"
        castShadow={quality.shadows}
        shadow-mapSize={[size, size]}
        shadow-radius={6}
        shadow-bias={-0.0004}
        shadow-normalBias={0.02}
        shadow-camera-near={0.5}
        shadow-camera-far={8}
        shadow-camera-left={-1.5}
        shadow-camera-right={1.5}
        shadow-camera-top={2.2}
        shadow-camera-bottom={-0.5}
      />
      <directionalLight position={[-2.2, 1.4, 1.8]} intensity={realistic ? 0.55 : 0.3} color="#cfe0ff" />
      <directionalLight position={[-0.8, 2.2, -2.6]} intensity={realistic ? 1.4 : 0.6} color="#ffd9e6" />
      <directionalLight position={[1.4, 1.6, -2.2]} intensity={realistic ? 0.9 : 0.35} color="#d6e4ff" />
    </>
  );
}
