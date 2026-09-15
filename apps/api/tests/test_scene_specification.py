from __future__ import annotations

import pytest
from hinaa_api.media.scene_specification import (
    ReferenceRole,
    SceneSpecification,
    compile_scene_specification,
)


def test_scene_specification_compiles_prompt_and_negative():
    spec = SceneSpecification(
        subject="Mikasa Ackerman",
        expression="determined",
        attire="survey corps uniform and dark red scarf",
        setting_environment="standing on Wall Maria at sunset",
        lighting="golden hour warm sunlight",
        composition="dramatic action pose, Dutch angle, motion blur",
        style_medium="anime",
        hard_constraints=["preserve facial identity and structure"],
    )

    prompt = spec.to_prompt()
    assert "Mikasa Ackerman" in prompt
    assert "determined expression" in prompt
    assert "survey corps uniform" in prompt
    assert "Wall Maria" in prompt
    assert "golden hour" in prompt
    assert "anime aesthetic" in prompt

    neg = spec.to_negative_prompt()
    assert "altered face" in neg
    assert "mismatched facial features" in neg
    assert "bad anatomy" in neg


def test_compile_scene_specification_extracts_identity_constraint():
    user_prompt = "generate Mikasa Ackerman fighting a titan, don't change her face"
    attachments = [{"id": "img_ref_1", "url": "https://example.com/mikasa_ref.png"}]

    spec = compile_scene_specification(user_prompt, attachments=attachments)

    assert spec.subject == "Mikasa Ackerman"
    assert "preserve facial identity and structure" in spec.hard_constraints
    assert spec.reference_roles.get("img_ref_1") == ReferenceRole.FACE_IDENTITY
