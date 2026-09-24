from __future__ import annotations

import asyncio

from hinaa_api.tools import image_generate


def test_image_generation_reports_local_comfyui_unavailable_before_queueing(monkeypatch) -> None:
    async def offline() -> bool:
        return False

    monkeypatch.setattr(image_generate.comfyui_provider, "health_check", offline)
    monkeypatch.setattr(image_generate, "cloud_image_available", lambda: False)

    result = asyncio.run(
        image_generate.image_generate_handler(
            image_generate.ImageGenerateParams(
                prompt="A warm companion workspace",
                userId="local-user",
                conversationId="local-conversation",
            )
        )
    )

    assert result["status"] == "error"
    assert result["code"] == "IMAGE_RENDERER_UNAVAILABLE"
    assert "127.0.0.1:8188" in result["error"]


def test_image_generation_prefers_local_comfyui_when_ready(monkeypatch) -> None:
    async def ready() -> bool:
        return True

    scheduled: list = []
    monkeypatch.setattr(image_generate.comfyui_provider, "health_check", ready)
    monkeypatch.setattr(
        image_generate.asyncio,
        "create_task",
        lambda task: (scheduled.append(task), task.close()),
    )

    result = asyncio.run(
        image_generate.image_generate_handler(
            image_generate.ImageGenerateParams(
                prompt="A warm companion workspace",
                userId="local-user",
                conversationId="local-conversation",
            )
        )
    )

    assert result["status"] == "processing"
    assert result["strategy"] == "independent-queue-variations"


def test_image_generation_uses_cloud_gateway_when_comfyui_offline(monkeypatch) -> None:
    async def offline() -> bool:
        return False

    monkeypatch.setattr(image_generate.comfyui_provider, "health_check", offline)
    monkeypatch.setattr(image_generate, "cloud_image_available", lambda: True)

    result = asyncio.run(
        image_generate.image_generate_handler(
            image_generate.ImageGenerateParams(
                prompt="A warm companion workspace",
                userId="local-user",
                conversationId="local-conversation",
            )
        )
    )

    assert result["status"] == "processing"
    assert result["strategy"] == "cloud-gateway-step-image"
    assert result["total"] == 1


def test_comfyui_workflow_keeps_each_variation_as_a_safe_single_latent() -> None:
    provider = image_generate.LocalComfyUIProvider(
        image_generate.ComfyUIConfig(base_url="http://127.0.0.1:8188")
    )

    workflow = provider._build_workflow(
        prompt="A calm anime companion in a futuristic workspace",
        negative_prompt="low quality",
        seed=42,
        width=768,
        height=768,
        filename_prefix="HINAA_test",
        mode="fast",
    )
    latent = next(node for node in workflow.values() if node.get("class_type") == "EmptyLatentImage")
    sampler = next(node for node in workflow.values() if node.get("class_type") == "KSampler")

    assert latent["inputs"]["batch_size"] == 1
    assert latent["inputs"]["width"] == 768
    assert latent["inputs"]["height"] == 768
    assert sampler["inputs"]["seed"] == 42


def test_image_handler_discloses_independent_queue_variations(monkeypatch) -> None:
    async def ready() -> bool:
        return True

    scheduled = []
    monkeypatch.setattr(image_generate.comfyui_provider, "health_check", ready)
    monkeypatch.setattr(image_generate.asyncio, "create_task", lambda task: (scheduled.append(task), task.close()))

    result = asyncio.run(
        image_generate.image_generate_handler(
            image_generate.ImageGenerateParams(
                prompt="Four distinct futuristic companion-workspace variations",
                count=4,
                userId="local-user",
            )
        )
    )

    assert result["status"] == "processing"
    assert result["total"] == 4
    assert result["strategy"] == "independent-queue-variations"
    assert scheduled
