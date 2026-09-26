"""The picture he points at has to be the picture the renderer receives.

His edit turn died on "Reference editing needs local ComfyUI running. Cloud
text-to-image fallback cannot preserve your reference" while a Magnific key
that takes `input_image` sat configured, and the weak brain that answered
paraphrased that as "no image generation models are configured". Measured
here without spending a credit: the refusal, the payload, and the bytes.
"""

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.providers.magnific import MagnificProvider
from hinaa_api.tools import image_generate

PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode("ascii")
REFERENCE = f"data:image/png;base64,{PNG_B64}"


def _settings(**keys) -> Settings:
    return Settings(_env_file=None, **keys)


def _params(**kw) -> image_generate.ImageGenerateParams:
    base = {"prompt": "make it darker", "userId": "owner-1", "count": 1, "mode": "quality"}
    base.update(kw)
    return image_generate.ImageGenerateParams(**base)


class _NoRows:
    def filter_by(self, *a, **k):
        return self

    def all(self):
        return []

    def first(self):
        return None


def _in_memory_db(monkeypatch, rows=None):
    """Every session the tool opens, backed by a dict of (model, id) -> row."""
    rows = rows if rows is not None else {}

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, model, key):
            return rows.get((getattr(model, "__name__", str(model)), key))

        def add(self, obj):
            return None

        def commit(self):
            return None

        def query(self, model):
            return _NoRows()

    monkeypatch.setattr(image_generate, "get_session_factory", lambda _settings: _Session)
    return rows


def _comfy_offline(monkeypatch):
    async def offline():
        return False

    monkeypatch.setattr(image_generate.comfyui_provider, "health_check", offline)


class _Gateway:
    def __init__(self, honours: bool):
        self._honours = honours

    def honours_reference_image(self):
        return self._honours


def _renderer(monkeypatch, *, cloud: bool, honours: bool):
    monkeypatch.setattr(image_generate, "cloud_image_available", lambda: cloud)
    monkeypatch.setattr(image_generate, "MagnificProvider", lambda _settings: _Gateway(honours))
    _in_memory_db(monkeypatch)
    monkeypatch.setattr(
        image_generate.asyncio,
        "create_task",
        lambda coro: coro.close(),
    )


# ─── what the gateway can actually do ────────────────────────────────────────


def test_the_capability_matches_the_contract_the_gateway_posts():
    both = MagnificProvider(_settings(MAGNIFIC_API_KEY="m-key", FREEPIK_API_KEY="f-key"))
    assert both._base_url() == "https://api.magnific.com"
    assert both.honours_reference_image() is True

    freepik_only = MagnificProvider(_settings(MAGNIFIC_API_KEY=None, FREEPIK_API_KEY="f-key"))
    assert freepik_only._base_url() == "https://api.freepik.com"
    # Its text-to-image payload has no input-image field at all.
    assert freepik_only.honours_reference_image() is False

    assert MagnificProvider(_settings(MAGNIFIC_API_KEY=None, FREEPIK_API_KEY=None)).honours_reference_image() is False


@pytest.mark.asyncio
async def test_a_reference_edit_posts_his_picture_not_just_his_words(monkeypatch):
    seen: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}") if request.content else {}
        seen.append((request.url.path, body))
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"task_id": "task-1"}})
        return httpx.Response(200, json={"data": {"status": "COMPLETED", "image_url": f"data:image/png;base64,{PNG_B64}"}})

    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original_client(transport=transport, **kw))

    provider = MagnificProvider(_settings(MAGNIFIC_API_KEY="m-key", FREEPIK_API_KEY=None, MAGNIFIC_POLL_SECONDS=0.001))
    result = await provider.generate("make it darker", reference_image_b64=REFERENCE)

    post_path, post_body = seen[0]
    assert post_path == "/v1/ai/text-to-image/flux-kontext-pro"
    assert post_body["input_image"] == REFERENCE
    assert result.image_urls


# ─── the refusal, and when it is a lie ───────────────────────────────────────


def test_an_edit_is_refused_only_when_nothing_can_carry_his_picture(monkeypatch):
    """The old guard refused every reference unless ComfyUI ran, in a deployment
    where the configured gateway takes one."""
    _comfy_offline(monkeypatch)
    _renderer(monkeypatch, cloud=True, honours=False)

    result = asyncio.run(image_generate.image_generate_handler(_params(reference_images=[REFERENCE])))

    assert result["code"] == "REFERENCE_RENDERER_UNAVAILABLE"
    assert "job_id" not in result
    assert "text only" in result["error"]
    # A configured gateway is never "no models configured".
    assert "no image generation models" not in result["error"].lower()


def test_a_reference_edit_files_a_job_when_the_gateway_takes_references(monkeypatch):
    _comfy_offline(monkeypatch)
    _renderer(monkeypatch, cloud=True, honours=True)

    result = asyncio.run(image_generate.image_generate_handler(_params(reference_images=[REFERENCE])))

    assert result["status"] == "processing"
    assert result["reference_applied"] is True
    assert result["renderer"] == "magnific-flux"


def test_a_plain_generate_still_needs_no_renderer_that_takes_pictures(monkeypatch):
    _comfy_offline(monkeypatch)
    _renderer(monkeypatch, cloud=True, honours=False)

    result = asyncio.run(image_generate.image_generate_handler(_params()))

    assert result["status"] == "processing"
    assert result["reference_applied"] is False


def test_two_references_are_still_refused_rather_than_half_used(monkeypatch):
    _renderer(monkeypatch, cloud=True, honours=True)

    result = asyncio.run(image_generate.image_generate_handler(_params(reference_images=[REFERENCE, REFERENCE])))

    assert result["code"] == "MULTI_REFERENCE_UNSUPPORTED"


# ─── the reference reaching the vendor as bytes ──────────────────────────────


def test_a_picture_from_his_own_grid_reaches_the_vendor_as_bytes(monkeypatch, tmp_path):
    """The serve route answers a file name as well as a job id, and the vendor
    cannot fetch a link to this machine either way."""
    (tmp_path / "freepik_1700_2.jpg").write_bytes(b"JPEG-BYTES")
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)
    _in_memory_db(monkeypatch)

    url, b64 = asyncio.run(image_generate._resolve_reference(_params(reference_images=["/api/v1/generated-images/freepik_1700_2.jpg"])))

    assert url is None
    assert b64.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(b64.split(",", 1)[1]) == b"JPEG-BYTES"


def test_a_job_id_reference_is_read_from_its_recorded_file(monkeypatch, tmp_path):
    picture = tmp_path / "HINAA_job-9_12.png"
    picture.write_bytes(b"PNG-BYTES")
    rows = _in_memory_db(monkeypatch, {
        ("ImageJob", "job-9"): SimpleNamespace(id="job-9", generation_set_id="set-1", file_path=str(picture)),
        ("GenerationSet", "set-1"): SimpleNamespace(user_id="owner-1"),
    })
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)

    url, b64 = asyncio.run(image_generate._resolve_reference(_params(reference_url="/v1/generated-images/job-9")))

    assert url is None and base64.b64decode(b64.split(",", 1)[1]) == b"PNG-BYTES"
    assert ("ImageJob", "job-9") in rows


def test_another_users_job_id_still_refuses_him(monkeypatch, tmp_path):
    picture = tmp_path / "HINAA_job-9_12.png"
    picture.write_bytes(b"PNG-BYTES")
    _in_memory_db(monkeypatch, {
        ("ImageJob", "job-9"): SimpleNamespace(id="job-9", generation_set_id="set-1", file_path=str(picture)),
        ("GenerationSet", "set-1"): SimpleNamespace(user_id="someone-else"),
    })

    with pytest.raises(HinaaError) as raised:
        asyncio.run(image_generate._resolve_reference(_params(reference_images=["/api/v1/generated-images/job-9"])))
    assert raised.value.code == "IMAGE_NOT_FOUND"


def test_a_generated_link_that_names_no_file_is_refused_not_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)
    _in_memory_db(monkeypatch)

    with pytest.raises(HinaaError) as raised:
        asyncio.run(image_generate._resolve_reference(_params(reference_images=["/api/v1/generated-images/freepik_gone.jpg"])))
    assert raised.value.code == "IMAGE_NOT_FOUND"


def test_a_reference_cannot_walk_out_of_the_image_store(monkeypatch, tmp_path):
    (tmp_path.parent / "outside.png").write_bytes(b"NOT-OURS")
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)
    _in_memory_db(monkeypatch)

    with pytest.raises(HinaaError):
        asyncio.run(image_generate._resolve_reference(
            _params(reference_images=[f"/api/v1/generated-images/{tmp_path.parent.name}/outside.png"]))
        )


def test_a_web_picture_stays_a_link_the_gateway_can_fetch(monkeypatch):
    _in_memory_db(monkeypatch)

    url, b64 = asyncio.run(image_generate._resolve_reference(_params(reference_images=["https://cdn.test/photo.jpg"])))

    assert (url, b64) == ("https://cdn.test/photo.jpg", None)
    # And a picture his browser encoded goes whole: the gateway reads a data URL
    # of his own, so re-encoding it here would only cost him detail.
    url, b64 = asyncio.run(image_generate._resolve_reference(_params(reference_images=[REFERENCE])))

    assert (url, b64) == (REFERENCE, None)


# ─── a reference the renderer cannot read ───────────────────────────────────
#
# Measured on flux-kontext-pro: posted as it arrives, the bare token `cda16831-…`
# cost a credit and came back "Invalid or corrupted image" in seven seconds, while
# the same picture sent as bytes or as a fetchable link edited. Nothing this server
# has should ever reach the vendor as an unreadable word.


def test_a_bare_job_id_is_his_own_picture_read_from_disk(monkeypatch, tmp_path):
    picture = tmp_path / "HINAA_job-9_12.png"
    picture.write_bytes(b"PNG-BYTES")
    _in_memory_db(monkeypatch, {
        ("ImageJob", "job-9"): SimpleNamespace(id="job-9", generation_set_id="set-1", file_path=str(picture)),
        ("GenerationSet", "set-1"): SimpleNamespace(user_id="owner-1"),
    })
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)

    url, b64 = asyncio.run(image_generate._resolve_reference(_params(reference_images=["job-9"])))

    assert url is None
    assert base64.b64decode(b64.split(",", 1)[1]) == b"PNG-BYTES"


def test_a_reference_that_names_nothing_is_refused_here_not_by_the_vendor(monkeypatch, tmp_path):
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)
    _in_memory_db(monkeypatch)

    with pytest.raises(HinaaError) as raised:
        asyncio.run(image_generate._resolve_reference(_params(reference_images=["not-a-picture"])))

    assert raised.value.code == "IMAGE_REFERENCE_UNREADABLE"
    assert "not-a-picture" in raised.value.message
    assert "Attach" in raised.value.message


def test_an_unreadable_reference_is_refused_before_a_job_is_filed(monkeypatch, tmp_path):
    """The promise was the damage: `reference_applied: true`, then a job that could
    only end "Image 1 failed" with no cause anywhere he could see it."""

    def nothing_may_be_filed(coro):
        coro.close()
        raise AssertionError("a render was started for a reference nothing can read")

    _comfy_offline(monkeypatch)
    _renderer(monkeypatch, cloud=True, honours=True)
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)
    monkeypatch.setattr(image_generate.asyncio, "create_task", nothing_may_be_filed)

    result = asyncio.run(image_generate.image_generate_handler(_params(reference_images=["not-a-picture"])))

    assert result["code"] == "IMAGE_REFERENCE_UNREADABLE"
    assert "job_id" not in result
    assert "Attach" in result["error"]


def test_his_own_picture_by_bare_job_id_still_files_the_job(monkeypatch, tmp_path):
    _comfy_offline(monkeypatch)
    _renderer(monkeypatch, cloud=True, honours=True)
    picture = tmp_path / "HINAA_job-9_12.png"
    picture.write_bytes(b"PNG-BYTES")
    _in_memory_db(monkeypatch, {
        ("ImageJob", "job-9"): SimpleNamespace(id="job-9", generation_set_id="set-1", file_path=str(picture)),
        ("GenerationSet", "set-1"): SimpleNamespace(user_id="owner-1"),
    })
    monkeypatch.setattr(image_generate, "_image_store", lambda: tmp_path)

    result = asyncio.run(image_generate.image_generate_handler(_params(reference_images=["job-9"])))

    assert result["status"] == "processing"
    assert result["reference_applied"] is True
