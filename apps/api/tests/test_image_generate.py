from __future__ import annotations

import asyncio

from hinaa_api.tools import image_generate


def test_image_generation_reports_local_comfyui_unavailable_before_queueing(monkeypatch) -> None:
    async def offline() -> bool:
        return False

    monkeypatch.setattr(image_generate.comfyui_provider, "health_check", offline)

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
    assert result["code"] == "COMFYUI_UNAVAILABLE"
    assert result["localOnly"] is True
    assert "127.0.0.1:8188" in result["error"]
