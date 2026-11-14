import shutil
import subprocess

import pytest

from hinaa_api.creative.assets.manager import CreativeAssetManager
from hinaa_api.creative.assets.video_validation import validate_video
from hinaa_api.creative.models import CreativeOperation


def store(manager, data):
    return manager.store_asset(data, "clip.mp4", CreativeOperation.TEXT_TO_VIDEO, "local-test", "1", tenant_id="test")


def test_padded_header_cannot_be_registered(tmp_path):
    manager = CreativeAssetManager(tmp_path)
    with pytest.raises(ValueError):
        store(manager, b"\x00\x00\x00\x18ftypisom" + bytes(2048))
    assert manager._assets == {}
    assert list(tmp_path.iterdir()) == []


def test_missing_decoder_fails_closed(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="requires ffprobe"):
        validate_video(bytes(1024), ".mp4")


@pytest.fixture
def real_video(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Real video acceptance requires ffmpeg and ffprobe")
    path = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=10", "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True, timeout=15)
    return path.read_bytes()


def test_real_video_registered_with_measured_metadata(tmp_path, real_video):
    manager = CreativeAssetManager(tmp_path / "assets")
    meta = store(manager, real_video)
    assert (meta.width, meta.height) == (64, 64)
    assert meta.duration_seconds == pytest.approx(1, abs=.1)
    assert meta.fps == 10
    assert manager.get_asset_bytes(meta.asset_id, "test") == real_video
    assert manager.get_asset_bytes(meta.asset_id, "other-user") is None


def test_truncated_video_is_rejected(real_video):
    with pytest.raises(ValueError):
        validate_video(real_video[:len(real_video)//2], ".mp4")


def test_registered_video_download_and_missing_file(tmp_path, real_video, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from hinaa_api.routers.creative_router import build_creative_router
    import hinaa_api.creative as creative
    manager = CreativeAssetManager(tmp_path / "assets")
    meta = store(manager, real_video)
    monkeypatch.setattr(creative, "creative_asset_manager", manager)
    app = FastAPI()
    app.include_router(build_creative_router(None))
    with TestClient(app) as client:
        url = f"/v1/creative/assets/{meta.asset_id}/download"
        response = client.get(url, headers={"X-Tenant-ID": "test"})
        assert response.status_code == 200
        assert response.content == real_video
        assert response.headers["content-type"] == "video/mp4"
        assert response.headers["etag"] == f'"{meta.sha256_hash}"'
        assert client.get(url, headers={"X-Tenant-ID": "other"}).status_code == 404
        manager.get_asset_path(meta.asset_id, "test").write_bytes(b"corrupted")
        assert client.get(url, headers={"X-Tenant-ID": "test"}).status_code == 409
        manager.get_asset_path(meta.asset_id, "test").unlink()
        assert client.get(url, headers={"X-Tenant-ID": "test"}).status_code == 404


def test_decode_failure_does_not_register(tmp_path, monkeypatch):
    import json
    calls = 0
    monkeypatch.setattr(shutil, "which", lambda name: name)
    def run(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(args, 0, json.dumps({"streams": [{"codec_type": "video", "width": 64, "height": 64, "duration": "1"}]}).encode())
        raise subprocess.TimeoutExpired("ffmpeg", 45)
    monkeypatch.setattr(subprocess, "run", run)
    manager = CreativeAssetManager(tmp_path)
    with pytest.raises(ValueError):
        store(manager, b"\x00\x00\x00\x18ftypisom" + bytes(2048))
    assert not manager._assets
    assert not list(tmp_path.iterdir())
