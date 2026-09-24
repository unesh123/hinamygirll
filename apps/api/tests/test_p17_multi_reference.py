from __future__ import annotations

import pytest
from hinaa_api.media.models import AssetKind
from hinaa_api.media.resolver import ResolvedMedia
from hinaa_api.prompts.models import PromptInput
from hinaa_api.prompts.assembly import assemble_prompt
from hinaa_api.models import TurnRequest, ToolExecutionRequest
from hinaa_api.tools.image_generate import ImageGenerateParams


def test_turn_request_accepts_multiple_attachments_with_roles():
    req = TurnRequest(
        sessionId="test-session",
        text="Blend these three images together",
        imageEngine="gemini-3.5-flash-image",
        voiceEngine="elevenlabs",
        attachments=[
            {
                "id": "att-1",
                "asset_id": "asset-sub-1",
                "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "kind": "image",
                "role": "subject",
                "filename": "model_pose.png",
            },
            {
                "id": "att-2",
                "asset_id": "asset-style-2",
                "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "kind": "image",
                "role": "style",
                "filename": "cyberpunk_palette.png",
            },
            {
                "id": "att-3",
                "asset_id": "asset-bg-3",
                "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "kind": "image",
                "role": "background",
                "filename": "tokyo_street.png",
            },
        ],
    )
    assert len(req.attachments) == 3
    assert req.attachments[0]["role"] == "subject"
    assert req.attachments[1]["role"] == "style"
    assert req.attachments[2]["role"] == "background"
    assert req.imageEngine == "gemini-3.5-flash-image"
    assert req.voiceEngine == "elevenlabs"


def test_prompt_assembly_with_multi_reference_roles():
    media_items = [
        ResolvedMedia(
            asset_id="asset-1",
            bytes_data=b"img1",
            mime_type="image/png",
            sha256="h1",
            role="subject",
            filename="subject.png",
        ),
        ResolvedMedia(
            asset_id="asset-2",
            bytes_data=b"img2",
            mime_type="image/png",
            sha256="h2",
            role="style",
            filename="style.png",
        ),
        ResolvedMedia(
            asset_id="asset-3",
            bytes_data=b"img3",
            mime_type="image/png",
            sha256="h3",
            role="background",
            filename="bg.png",
        ),
    ]

    inp = PromptInput(
        companion_id="hinaa",
        interaction_mode="rest",
        user_text="Render the subject in this style with this background",
        attachments=tuple(media_items),
    )
    pkg = assemble_prompt(inp)

    # Prompt assembly must succeed and have valid layers
    assert len(pkg.layers) > 0


def test_image_generate_params_accepts_engine_and_references():
    # ImageGenerateParams requires userId (filled by dispatcher at runtime).
    # In unit tests we supply it directly to verify engine + references are accepted.
    params = ImageGenerateParams(
        prompt="Anime heroine standing in neon rain",
        userId="test-user",
        aspectRatio="16:9",
        engine="gemini-3.5-flash-image",
        references=[
            {"url": "https://example.com/pose.png", "role": "pose"},
            {"url": "https://example.com/character.png", "role": "character"},
            {"url": "https://example.com/palette.png", "role": "style"},
        ],
    )
    assert params.engine == "gemini-3.5-flash-image"
    assert len(params.references) == 3
    assert params.references[1]["role"] == "character"


def test_image_generate_params_references_empty_by_default():
    params = ImageGenerateParams(prompt="Simple background", userId="u1")
    assert params.engine is None
    assert params.references == []


def test_tool_execution_request_preserves_engine_and_references():
    req = ToolExecutionRequest(
        toolName="image_generate",
        parameters={
            "prompt": "Cyberpunk warrior",
            "engine": "comfyui-local",
            "references": [
                {"url": "asset://face1", "role": "face"},
                {"url": "asset://style2", "role": "style"},
            ],
        },
        imageEngine="comfyui-local",
    )
    assert req.imageEngine == "comfyui-local"
    assert req.parameters["engine"] == "comfyui-local"
    assert len(req.parameters["references"]) == 2
