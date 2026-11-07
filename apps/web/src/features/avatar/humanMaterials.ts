import * as THREE from "three";

const SKIN = /skin|body|face|head|arm|leg|hand|neck|torso/i;
const HAIR = /hair|brow|lash/i;
const EYE = /eye(?!lash|brow)|cornea/i;

/**
 * Upgrade PBR materials of a realistic GLB for believable skin, hair and eyes.
 * three has no true subsurface scattering; sheen with a warm tint approximates the soft skin
 * rim, and a clearcoat gives the cornea its wet highlight. Non-standard materials (unlit, toon)
 * and already-physical materials are returned untouched.
 */
export function enhanceHumanMaterial(material: THREE.Material, meshName = ""): THREE.Material {
  if (!(material instanceof THREE.MeshStandardMaterial) || material instanceof THREE.MeshPhysicalMaterial) return material;
  const label = `${material.name} ${meshName}`;
  const physical = new THREE.MeshPhysicalMaterial();
  // Physical.copy() expects physical fields on the source; copy the shared standard fields only.
  THREE.MeshStandardMaterial.prototype.copy.call(physical, material);
  physical.name = material.name;
  if (EYE.test(label)) {
    physical.clearcoat = 1;
    physical.clearcoatRoughness = 0.04;
    physical.roughness = Math.min(physical.roughness, 0.2);
  } else if (HAIR.test(label)) {
    physical.sheen = 0.6;
    physical.sheenRoughness = 0.5;
    physical.sheenColor = new THREE.Color("#ffe6dc");
    physical.roughness = Math.max(0.35, Math.min(physical.roughness, 0.7));
  } else if (SKIN.test(label)) {
    physical.sheen = 0.4;
    physical.sheenRoughness = 0.6;
    physical.sheenColor = new THREE.Color("#ffb7a0");
    physical.roughness = Math.max(0.42, Math.min(physical.roughness, 0.7));
    physical.specularIntensity = 0.6;
  }
  material.dispose();
  return physical;
}

export function enhanceHumanMaterials(root: THREE.Object3D): void {
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh || !mesh.material) return;
    mesh.material = Array.isArray(mesh.material)
      ? mesh.material.map((m) => enhanceHumanMaterial(m, mesh.name))
      : enhanceHumanMaterial(mesh.material, mesh.name);
  });
}
