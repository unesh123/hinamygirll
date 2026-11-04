import asyncio
import io
import json

import httpx
import pytest
from PIL import Image

from hinaa_api.providers.local_comfyui import ComfyUIConfig, LocalComfyUIProvider


def workflow():
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "selected.safetensors"}},
        "2": {"class_type": "SaveImage", "inputs": {}},
    }


@pytest.mark.parametrize("nodes,models,ready", [
    (["CheckpointLoaderSimple", "SaveImage"], ["selected.safetensors"], True),
    (["CheckpointLoaderSimple"], ["selected.safetensors"], False),
    (["CheckpointLoaderSimple", "SaveImage"], ["other.safetensors"], False),
])
def test_workflow_readiness_requires_nodes_and_selected_models(nodes, models, ready, monkeypatch):
    async def run():
        provider = LocalComfyUIProvider()
        await provider._http.aclose()
        catalog = {name: {"input": {"required": {"ckpt_name": [models]}}} for name in nodes}
        provider._http = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=catalog)), base_url="http://127.0.0.1:8188")
        monkeypatch.setattr(provider, "load_base_workflow", workflow)
        monkeypatch.setattr(provider, "load_ultra_workflow", workflow)
        try:
            result = await provider.workflow_readiness()
            assert result["serverReachable"]
            assert result["ready"] is ready
            if "SaveImage" not in nodes:
                assert result["workflows"]["fast"]["missingNodes"] == ["SaveImage"]
            if "selected.safetensors" not in models:
                assert result["workflows"]["fast"]["missingModels"][0]["file"] == "selected.safetensors"
        finally:
            await provider._http.aclose()

    asyncio.run(run())


def test_custom_workflow_path_preserves_shipped_templates(tmp_path):
    exported = tmp_path / "custom-api.json"
    exported.write_text(json.dumps(workflow()))
    provider = LocalComfyUIProvider(ComfyUIConfig(workflow_path=str(exported)))
    try:
        assert provider.load_base_workflow() == workflow()
    finally:
        asyncio.run(provider._http.aclose())


@pytest.mark.parametrize("valid", [True, False])
def test_downloaded_output_is_validated_before_file_registration(valid, tmp_path, monkeypatch):
    async def run():
        root = tmp_path / "api" / "hinaa_api" / "providers"
        root.mkdir(parents=True)
        monkeypatch.setattr("hinaa_api.providers.local_comfyui.__file__", str(root / "local_comfyui.py"))
        output = io.BytesIO()
        Image.new("RGB", (8, 8)).save(output, format="PNG")
        content = output.getvalue() if valid else b"<html>provider error</html>"
        provider = LocalComfyUIProvider()
        await provider._http.aclose()
        provider._http = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=content)), base_url="http://127.0.0.1:8188")
        try:
            outputs = {"2": {"images": [{"filename": "image.png"}]}}
            if valid:
                files = await provider._download_outputs(outputs)
                assert len(files) == 1
                with Image.open(files[0]) as image:
                    assert image.size == (8, 8)
            else:
                with pytest.raises(ValueError, match="invalid image"):
                    await provider._download_outputs(outputs)
                assert not list(tmp_path.rglob("*.png"))
        finally:
            await provider._http.aclose()

    asyncio.run(run())
