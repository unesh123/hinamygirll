import * as THREE from "three";
import { VRM, VRMUtils } from "@pixiv/three-vrm";

/**
 * Deeply disposes all Three.js geometries, textures, materials, and VRM listeners
 * to prevent GPU context loss and VRAM leakage when switching models.
 */
export function disposeVrmModel(vrm: VRM | null): void {
  if (!vrm) return;
  try {
    VRMUtils.deepDispose(vrm.scene);
    vrm.scene.traverse((obj) => {
      if ((obj as THREE.Mesh).isMesh) {
        const mesh = obj as THREE.Mesh;
        if (mesh.geometry) {
          mesh.geometry.dispose();
        }
        if (Array.isArray(mesh.material)) {
          mesh.material.forEach((mat) => {
            disposeMaterial(mat);
          });
        } else if (mesh.material) {
          disposeMaterial(mesh.material);
        }
      }
    });
  } catch (err) {
    console.warn("Non-fatal error during VRM disposal:", err);
  }
}

function disposeMaterial(mat: THREE.Material): void {
  mat.dispose();
  for (const key of Object.keys(mat)) {
    const value = (mat as unknown as Record<string, unknown>)[key];
    if (value && typeof value === "object" && "isTexture" in value && (value as THREE.Texture).isTexture) {
      (value as THREE.Texture).dispose();
    }
  }
}
