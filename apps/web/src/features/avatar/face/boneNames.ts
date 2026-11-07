export type BodyBoneRole =
  | "hips" | "spine" | "chest" | "neck" | "head" | "shoulderLeft" | "shoulderRight";

/**
 * Map a rig bone name (Mixamo, Character Creator, ReadyPlayerMe, generic) to a role.
 * Matching ignores common prefixes such as `mixamorig:` and `CC_Base_`.
 */
export function matchBodyBone(rawName: string): BodyBoneRole | null {
  const n = rawName
    .toLowerCase()
    .replace(/^(mixamorig[:_]?|cc_base_|bip01[ _]?|armature[|_.]?)/, "")
    .replace(/[\s_.\-:]/g, "");
  switch (n) {
    case "hips": case "pelvis": case "hip": return "hips";
    case "spine": case "spine01": case "waist": return "spine";
    case "spine1": case "spine02": case "spine2": case "chest": case "upperchest": case "spine03": return "chest";
    case "neck": case "neck1": return "neck";
    case "head": return "head";
    case "leftshoulder": case "lclavicle": case "clavicleleft": case "shoulderl": case "claviclel": return "shoulderLeft";
    case "rightshoulder": case "rclavicle": case "clavicleright": case "shoulderr": case "clavicler": return "shoulderRight";
    default: return null;
  }
}
