"""A render that pays the vendor has to come back as a picture.

Measured on the real POST /v1/tools/execute path: every quality-mode job ended
`status: failed` with no file and no line in the log. The upscale pass returns
an asset stored on this server, and the caller handed that object to the
downloader; the TypeError then vanished into a bare `except: pass`.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hinaa_api.media.models import AssetRef, MediaResult
from hinaa_api.persistence.orm import GenerationSet, ImageJob
from hinaa_api.providers.magnific import MagnificError
from hinaa_api.tools import image_generate

RENDER = b"RENDER-BYTES"
UPSCALED = b"UPSCALED-BYTES-MUCH-LARGER"
RENDER_URL = "https://cdn.test/render.png"


def _params(**kw) -> image_generate.ImageGenerateParams:
    base = {
        "prompt": "a red mug on a table",
        "userId": "owner-1",
        "count": 1,
        "mode": "quality",
        "enhance": False,
        "upscale": True,
    }
    base.update(kw)
    return image_generate.ImageGenerateParams(**base)


def _db(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    GenerationSet.metadata.create_all(engine, tables=[GenerationSet.__table__, ImageJob.__table__])
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(image_generate, "get_session_factory", lambda _settings: factory)
    with factory() as session:
        session.add(GenerationSet(id="set-1", user_id="owner-1", prompt="a red mug", workflow_mode="cloud"))
        session.commit()
    return factory


class _Cloud:
    """Stands in for MagnificProvider with the contract it actually has."""

    def __init__(self, *, upscale_result=None, upscale_error=None, download_error=None):
        self.calls: list[object] = []
        self.settings = SimpleNamespace(
            magnific_base_url="https://api.test",
            magnific_model_fast="flux-fast",
            magnific_model_quality="flux-quality",
        )
        self.asset_store = SimpleNamespace(read_bytes=self._read_asset)
        self._upscale_result = upscale_result
        self._upscale_error = upscale_error
        self._download_error = download_error

    def _read_asset(self, asset_id: str) -> bytes:
        self.calls.append(("read_asset", asset_id))
        return UPSCALED

    def available(self) -> bool:
        return True

    async def generate(self, prompt: str, **_kwargs):
        self.calls.append("generate")
        return SimpleNamespace(image_urls=[RENDER_URL], provider="magnific:text-to-image")

    async def upscale(self, source: str, **_kwargs):
        self.calls.append(("upscale", source))
        if self._upscale_error is not None:
            raise self._upscale_error
        return self._upscale_result

    async def download(self, url: str) -> bytes:
        self.calls.append(("download", url))
        if self._download_error is not None:
            raise self._download_error
        return RENDER


def _run(monkeypatch, cloud, tmp_path, **params_kw):
    factory = _db(monkeypatch)
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)
    monkeypatch.setattr(image_generate, "MagnificProvider", lambda _settings: cloud)
    monkeypatch.setattr("hinaa_api.providers.stability_ai.StabilityAIProvider.available", lambda self: False)
    asyncio.run(image_generate.run_image_job("set-1", _params(**params_kw)))
    with factory() as session:
        return session.query(ImageJob).one()


def _upscaled_asset() -> MediaResult:
    return MediaResult(
        operation="upscale",
        provider="magnific:upscale",
        asset_ref=AssetRef(
            id="asset_abc123",
            mime_type="image/png",
            size_bytes=len(UPSCALED),
            sha256="0" * 64,
            public_url="/v1/assets/asset_abc123/file",
        ),
    )


def test_the_upscaled_asset_is_read_from_the_store_and_written_to_disk(monkeypatch, tmp_path):
    cloud = _Cloud(upscale_result=_upscaled_asset())
    job = _run(monkeypatch, cloud, tmp_path)

    assert job.status == "completed"
    assert job.file_path is not None
    assert open(job.file_path, "rb").read() == UPSCALED
    # His picture is the enlarged one, not the render the pass was meant to improve.
    assert ("read_asset", "asset_abc123") in cloud.calls
    # A route on this server is not something the downloader can fetch.
    assert "download" not in [call if isinstance(call, str) else call[0] for call in cloud.calls]


def test_an_upscale_that_returns_a_plain_url_is_still_delivered(monkeypatch, tmp_path):
    cloud = _Cloud(upscale_result="https://cdn.test/upscaled.png")
    job = _run(monkeypatch, cloud, tmp_path)

    assert job.status == "completed"
    assert ("download", "https://cdn.test/upscaled.png") in cloud.calls
    assert open(job.file_path, "rb").read() == RENDER


def test_a_failing_upscale_pass_keeps_the_render_he_paid_for(monkeypatch, tmp_path):
    """The second pass is a bonus. Losing the first picture would be worse."""
    cloud = _Cloud(upscale_error=MagnificError("IMAGE_PROVIDER_ERROR", "HTTP 503"))
    job = _run(monkeypatch, cloud, tmp_path)

    assert job.status == "completed"
    assert open(job.file_path, "rb").read() == RENDER


def test_an_upscale_that_returns_nothing_at_all_still_delivers_the_render(monkeypatch, tmp_path):
    cloud = _Cloud(upscale_result=None)
    job = _run(monkeypatch, cloud, tmp_path)

    assert job.status == "completed"
    assert open(job.file_path, "rb").read() == RENDER


def test_a_render_that_cannot_be_saved_reports_the_cause(monkeypatch, tmp_path, caplog):
    """Silent failure is what made this undiscoverable for a whole wave of credits."""
    cloud = _Cloud(upscale_result=None, download_error=MagnificError("IMAGE_PROVIDER_ERROR", "HTTP 502"))
    with caplog.at_level(logging.WARNING, logger="hinaa.image_generate"):
        job = _run(monkeypatch, cloud, tmp_path)

    assert job.status == "failed"
    assert job.file_path is None
    assert cloud.calls.count("generate") == 1
    causes = [record.getMessage() for record in caplog.records]
    assert any(job.id in cause and "HTTP 502" in cause for cause in causes), causes


def test_a_reference_nothing_can_read_bills_nobody_and_leaves_a_trace(monkeypatch, tmp_path, caplog):
    """Measured live: the token was posted to flux-kontext-pro, cost a credit, and
    the client was left with "Image 1 failed" and no line in any log."""
    cloud = _Cloud(upscale_result=_upscaled_asset())
    factory = _db(monkeypatch)
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)
    monkeypatch.setattr(image_generate, "MagnificProvider", lambda _settings: cloud)

    with caplog.at_level(logging.WARNING, logger="hinaa.image_generate"):
        asyncio.run(image_generate.run_image_job("set-1", _params(reference_images=["cda16831-702c-4abf-96f0"])))

    assert cloud.calls == []
    with factory() as session:
        assert session.query(ImageJob).one().status == "failed"
    causes = [record.getMessage() for record in caplog.records]
    assert any("set-1" in cause for cause in causes), causes
