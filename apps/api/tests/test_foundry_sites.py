"""Tests for HINAA Foundry (Phase 6): multi-file generator, WCAG gate, SQLite CRUD, ZIP & router."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import get_settings
from hinaa_api.foundry.service import FoundryService, run_quality_gate
from hinaa_api.foundry.tokens import FOUNDRY_PALETTES, FoundryPalette
from hinaa_api.main import create_app


def test_foundry_palettes_meet_wcag_aa():
    svc_palettes = FOUNDRY_PALETTES
    assert len(svc_palettes) >= 4
    for name, pal in svc_palettes.items():
        gate = run_quality_gate(
            {"index.html": '<html><body><header></header><main id="work"><h1>Hi</h1></main><footer></footer></body></html>'},
            pal,
        )
        assert gate.passed, f"Palette {name} failed WCAG AA: {gate.errors}"
        assert gate.contrast_body >= 4.5
        assert gate.contrast_cta >= 4.5


def test_foundry_quality_gate_rejects_broken_html_and_low_contrast():
    bad_palette = FoundryPalette(
        name="low",
        bg="#777777",
        surface="#888888",
        text="#999999",
        muted="#888888",
        accent="#aaaaaa",
        accent_text="#ffffff",
        border="#999999",
    )
    bad_files = {
        "index.html": (
            '<html><body><a href="#missing-section">Go</a>'
            '<h1>One</h1><h1>Two</h1><img src="https://evil.example/img.png">'
            "<p>Lorem ipsum dolor</p></body></html>"
        )
    }
    res = run_quality_gate(bad_files, bad_palette)
    assert res.passed is False
    joined = " | ".join(res.errors)
    assert "body contrast" in joined
    assert "CTA contrast" in joined
    assert "expected exactly 1 <h1>" in joined
    assert "lorem ipsum" in joined
    assert "external http(s) img" in joined
    assert "unresolved anchor #missing-section" in joined


def test_foundry_archetypes_brand_logos_and_idempotent_revise(tmp_path):
    svc = FoundryService(db_path=tmp_path / "foundry.db")

    bakery = svc.create_site("Sunrise Bakery in Portland selling sourdough loaves")
    assert bakery.archetype == "cafe_roastery"
    assert bakery.brand == "Sunrise Bakery"
    assert bakery.address == "Portland"
    assert "Trusted by" not in bakery.files["index.html"]

    studio = svc.create_site(
        "Kurogane Designer Portfolio in Tokyo",
        palette="violet",
        logos=["Studio One", "Pixel Lab"],
    )
    assert studio.archetype == "portfolio"
    film_site = svc.create_site("Kurogane Motion Film Reel")
    assert film_site.archetype == "studio"
    assert "Studio One" in studio.files["index.html"]
    assert "Pixel Lab" in studio.files["index.html"]

    rev1 = svc.revise_site(studio.site_id, palette="emerald", tagline="Senior kinetic director")
    assert rev1 is not None and rev1.revision == 2
    assert rev1.brand == studio.brand
    assert rev1.palette_name == "emerald"

    rev2 = svc.revise_site(studio.site_id, tagline="Updated reel and archive")
    assert rev2 is not None and rev2.revision == 3
    assert rev2.brand == studio.brand

    html_preview = svc.render_self_contained_preview_html(studio.site_id)
    assert html_preview is not None and "<style>" in html_preview and "<script>" in html_preview

    zip_res = svc.build_zip_bytes(studio.site_id)
    assert zip_res is not None
    raw_zip, digest = zip_res
    assert len(digest) == 64
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as zf:
        assert set(zf.namelist()) >= {"index.html", "styles.css", "app.js"}


def test_foundry_http_endpoints_crud_preview_zip(tmp_path, monkeypatch):
    import hinaa_api.foundry.service as foundry_mod

    monkeypatch.setattr(foundry_mod, "_FOUNDRY_SINGLETON", FoundryService(db_path=tmp_path / "api_foundry.db"))
    app = create_app(get_settings())
    with TestClient(app) as client:
        res = client.post(
            "/api/v1/foundry/sites",
            json={"brief": "Horizon AI Consultancy in Austin", "palette": "obsidian"},
        )
        assert res.status_code == 200
        created = res.json()
        site_id = created["site_id"]
        assert created["archetype"] == "agency"
        assert created["previewUrl"] == f"/api/v1/foundry/sites/{site_id}/preview"

        prev = client.get(created["previewUrl"])
        assert prev.status_code == 200
        assert "Horizon" in prev.text

        listed = client.get("/api/v1/foundry/sites")
        assert listed.status_code == 200
        assert any(item["site_id"] == site_id for item in listed.json()["sites"])

        revised = client.post(
            f"/api/v1/foundry/sites/{site_id}/revise",
            json={"palette": "ivory", "tagline": "Enterprise AI Systems"},
        )
        assert revised.status_code == 200
        assert revised.json()["revision"] == 2

        zip_resp = client.get(created["downloadUrl"])
        assert zip_resp.status_code == 200
        assert zip_resp.headers["content-type"] == "application/zip"

        deleted = client.delete(f"/api/v1/foundry/sites/{site_id}")
        assert deleted.status_code == 200 and deleted.json()["deleted"] is True
        assert client.get(f"/api/v1/foundry/sites/{site_id}").status_code == 404
