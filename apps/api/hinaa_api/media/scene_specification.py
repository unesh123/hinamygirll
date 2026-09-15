from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReferenceRole(str, Enum):
    FACE_IDENTITY = "FACE_IDENTITY"
    STYLE_REFERENCE = "STYLE_REFERENCE"
    POSE_REFERENCE = "POSE_REFERENCE"
    COMPOSITION_REFERENCE = "COMPOSITION_REFERENCE"


@dataclass
class SceneSpecification:
    """SceneSpecification V3: Structured prompt and generation constraint contract."""
    subject: str
    character_details: list[str] = field(default_factory=list)
    expression: str = "neutral"
    attire: str = ""
    setting_environment: str = ""
    lighting: str = ""
    composition: str = ""
    style_medium: str = "anime"
    hard_constraints: list[str] = field(default_factory=list)
    negative_prompt: str = ""
    reference_roles: dict[str, ReferenceRole] = field(default_factory=dict)

    def to_prompt(self) -> str:
        """Compile structured fields into a cohesive, high-quality diffusion prompt."""
        parts: list[str] = [self.subject]
        if self.character_details:
            parts.extend(self.character_details)
        if self.expression and self.expression != "neutral":
            parts.append(f"{self.expression} expression")
        if self.attire:
            parts.append(self.attire)
        if self.setting_environment:
            parts.append(self.setting_environment)
        if self.lighting:
            parts.append(self.lighting)
        if self.composition:
            parts.append(self.composition)

        # Style suffix
        style_suffixes = {
            "anime": "anime aesthetic, sharp lineart, vibrant colors, masterpiece, 8k uhd",
            "realistic": "photorealistic, natural skin texture, 8k uhd, dslr photo, sharp focus",
            "cinematic": "cinematic movie still, dramatic shadows, 35mm film, anamorphic lens",
            "3d-art": "3d render, octane render, volumetric lighting, subsurface scattering",
            "watercolor": "watercolor painting, delicate brushstrokes, paper texture, soft pigment",
        }
        suffix = style_suffixes.get(self.style_medium.lower(), "detailed digital art, masterpiece")
        parts.append(suffix)

        return ", ".join(p.strip(" ,") for p in parts if p.strip(" ,"))

    def to_negative_prompt(self) -> str:
        """Compile negative prompt including protection for hard constraints."""
        base_negatives = [
            "blurry", "low quality", "artifacts", "watermark", "deformed",
            "bad anatomy", "disfigured", "jpeg noise", "oversaturated", "text overlay"
        ]
        if self.negative_prompt:
            base_negatives.insert(0, self.negative_prompt)

        # Hard constraints enforcement in negative space
        for hc in self.hard_constraints:
            lower = hc.lower()
            if "face" in lower or "facial" in lower:
                base_negatives.extend(["altered face", "mismatched facial features", "different face", "distorted face"])
            if "hair" in lower:
                base_negatives.extend(["different hair color", "mismatched hairstyle"])
            if "limb" in lower or "hand" in lower:
                base_negatives.extend(["extra limbs", "extra fingers", "mutated hands", "missing fingers"])

        # Style negative guards
        if self.style_medium == "anime":
            base_negatives.extend(["photorealistic", "3d render", "plastic skin"])
        elif self.style_medium == "realistic":
            base_negatives.extend(["anime", "cartoon", "illustration", "cgi", "drawing"])

        return ", ".join(dict.fromkeys(base_negatives))


_IDENTITY_PRESERVATION_PATTERNS = [
    re.compile(r"\b(?:don'?t|do\s+not|never)\s+change\s+(?:her|his|their|the)\s+face\b", re.I),
    re.compile(r"\b(?:preserve|keep|maintain)\s+(?:the\s+same\s+)?(?:face|facial\s+features|appearance|identity)\b", re.I),
    re.compile(r"\b(?:same\s+face|don'?t\s+alter\s+face)\b", re.I),
]


def compile_scene_specification(
    prompt: str,
    *,
    state: Any | None = None,
    attachments: list[dict[str, Any]] | None = None,
    style_override: str | None = None,
) -> SceneSpecification:
    """Extracts structured scene specification from prompt, dialogue state, and attachments."""
    cleaned = prompt.strip()
    lowered = cleaned.lower()

    # 1. Subject extraction
    from hinaa_api.media.search_intelligence import canonical_entity_from_text, _profile_from_active
    prof = canonical_entity_from_text(prompt)
    if not prof and state and getattr(state, "active_topic", None):
        prof = _profile_from_active(state.active_topic)

    subject = prof.canonical_name if prof else cleaned

    # 2. Style detection
    style = style_override or "anime"
    if not style_override:
        if re.search(r"\b(realistic|photorealistic|photo\s+real|dslr)\b", lowered):
            style = "realistic"
        elif re.search(r"\b(cinematic|movie\s+still|film)\b", lowered):
            style = "cinematic"
        elif re.search(r"\b(3d|render|octane)\b", lowered):
            style = "3d-art"
        elif re.search(r"\b(watercolor|painting|canvas)\b", lowered):
            style = "watercolor"

    # 3. Expression detection
    expression = "neutral"
    for exp in ("smiling", "happy", "laughing", "sad", "crying", "angry", "furious", "surprised", "thinking", "determined", "blushing"):
        if re.search(rf"\b{exp}\b", lowered):
            expression = exp
            break

    # 4. Lighting detection
    lighting = ""
    if re.search(r"\b(golden\s+hour|sunset\s+glow)\b", lowered):
        lighting = "golden hour warm sunlight"
    elif re.search(r"\b(neon|cyberpunk\s+glow)\b", lowered):
        lighting = "vibrant neon rim lighting"
    elif re.search(r"\b(dramatic|chiaroscuro|heavy\s+shadows)\b", lowered):
        lighting = "dramatic directional lighting with deep contrast"
    elif re.search(r"\b(soft|diffuse|ambient)\b", lowered):
        lighting = "soft diffused ambient light"

    # 5. Composition / Camera angle
    composition = ""
    if re.search(r"\b(close-?up|portrait)\b", lowered):
        composition = "close-up portrait framing, shallow depth of field"
    elif re.search(r"\b(full\s+body|wide\s+shot)\b", lowered):
        composition = "full body dynamic view"
    elif re.search(r"\b(action|fighting|combat)\b", lowered):
        composition = "dynamic action pose, Dutch angle, motion blur"

    # 6. Hard constraints extraction
    hard_constraints: list[str] = []
    for pat in _IDENTITY_PRESERVATION_PATTERNS:
        if pat.search(lowered):
            hard_constraints.append("preserve facial identity and structure")
            break

    # 7. Reference roles mapping
    reference_roles: dict[str, ReferenceRole] = {}
    if attachments:
        for idx, att in enumerate(attachments):
            att_id = att.get("id") or att.get("url") or f"ref_{idx}"
            explicit_role = att.get("role")
            if explicit_role:
                try:
                    reference_roles[att_id] = ReferenceRole(explicit_role)
                except ValueError:
                    reference_roles[att_id] = ReferenceRole.STYLE_REFERENCE
            elif hard_constraints and idx == 0:
                reference_roles[att_id] = ReferenceRole.FACE_IDENTITY
            else:
                reference_roles[att_id] = ReferenceRole.STYLE_REFERENCE

    return SceneSpecification(
        subject=subject,
        expression=expression,
        lighting=lighting,
        composition=composition,
        style_medium=style,
        hard_constraints=hard_constraints,
        reference_roles=reference_roles,
    )
