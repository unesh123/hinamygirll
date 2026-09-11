from __future__ import annotations

import asyncio
import base64
import io

import httpx
import pytest
from PIL import Image

from hinaa_api.providers.local_comfyui import LocalComfyUIProvider
from hinaa_api.tools import image_generate


def reference_image() -> str:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(output, "PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def test_reference_pixels_reach_sampler_for_both_workflows():
    provider = LocalComfyUIProvider()
    for mode in ("quality", "ultra"):
        workflow = provider._build_workflow(
            prompt="Make the background blue", negative_prompt="", seed=12,
            width=768, height=768, filename_prefix="test", mode=mode,
            reference_name="reference.png",
        )
        sampler = next(node for node in workflow.values() if node["class_type"] == "KSampler")
        encoder = workflow[sampler["inputs"]["latent_image"][0]]
        assert encoder["class_type"] == "VAEEncode"
        scaler = workflow[encoder["inputs"]["pixels"][0]]
        loader = workflow[scaler["inputs"]["image"][0]]
        assert loader["inputs"]["image"] == "reference.png"
        assert 0 < sampler["inputs"]["denoise"] < 1


def test_reference_upload_is_multipart_and_precedes_prompt():
    calls = []

    def handle(request):
        calls.append(request.url.path)
        if request.url.path == "/system_stats":
            return httpx.Response(200, json={})
        if request.url.path == "/upload/image":
            assert "multipart/form-data" in request.headers["content-type"]
            assert b"\x89PNG" in request.content
            return httpx.Response(200, json={"name": "reference.png", "subfolder": "input"})
        assert request.url.path == "/prompt"
        assert b"input/reference.png" in request.content
        return httpx.Response(200, json={"prompt_id": "p-1"})

    async def run():
        provider = LocalComfyUIProvider()
        await provider._http.aclose()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle), base_url="http://localhost") as client:
            provider._http = client
            assert await provider.enqueue_prompt(prompt="Blue background", reference_image=reference_image()) == "p-1"

    asyncio.run(run())
    assert calls == ["/system_stats", "/upload/image", "/prompt"]


@pytest.mark.parametrize("reference", ["https://example.com/a.png", "data:image/png;base64,broken", "data:image/svg+xml;base64,PHN2Zz4="])
def test_invalid_reference_rejected_without_fetching(reference):
    with pytest.raises(ValueError):
        LocalComfyUIProvider.validate_reference(reference)


def test_offline_reference_does_not_silently_generate_unrelated_image(monkeypatch):
    async def offline():
        return False

    monkeypatch.setattr(image_generate.comfyui_provider, "health_check", offline)
    result = asyncio.run(image_generate.image_generate_handler(image_generate.ImageGenerateParams(
        prompt="Change the background", userId="local-user", reference_images=[reference_image()],
    )))
    assert result["code"] == "REFERENCE_RENDERER_UNAVAILABLE"
    assert "job_id" not in result


def test_multiple_references_are_not_silently_discarded():
    result = asyncio.run(image_generate.image_generate_handler(image_generate.ImageGenerateParams(
        prompt="Combine these", userId="local-user", reference_images=[reference_image(), reference_image()],
    )))
    assert result["code"] == "MULTI_REFERENCE_UNSUPPORTED"
