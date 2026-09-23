"""The artifact library must report what is on disk, not what was indexed.

The library used to list ``.metadata.json`` sidecars, so every document whose
writer failed to record one was invisible: 161 rendered PDFs sat in the
documents root while the API listed a dozen. These tests pin the file itself as
the unit of truth and the sidecar as optional description.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hinaa_api.artifacts import inventory
from hinaa_api.tools.browser import artifact_lookup

PDF_BYTES = b"%PDF-1.4\n% test fixture\n%%EOF\n"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def _write(path: Path, payload: bytes, when: float) -> Path:
    path.write_bytes(payload)
    os.utime(path, (when, when))
    return path


@pytest.fixture
def documents_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "documents"
    root.mkdir()
    monkeypatch.setattr(inventory, "document_roots", lambda: [root])
    return root


@pytest.fixture
def images_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "images"
    root.mkdir()
    monkeypatch.setattr(inventory, "image_roots", lambda: [root])
    return root


def test_orphan_document_without_a_sidecar_is_still_listed(documents_root: Path) -> None:
    _write(documents_root / "k7q2f1_city-climate-brief.pdf", PDF_BYTES, 1_700_000_000)

    entries = inventory.list_document_artifacts()

    assert len(entries) == 1
    entry = entries[0]
    assert entry["indexed"] is False
    assert entry["format"] == "pdf"
    # The random doc id prefix is dropped; a guess derived from the name beats
    # showing the raw filename, and `indexed` tells the UI it is a guess.
    assert entry["title"] == "City Climate Brief"
    assert entry["pageCount"] is None
    assert entry["downloadUrl"] == "/api/v1/generated-docs/k7q2f1_city-climate-brief"


def test_sidecar_title_and_date_beat_the_filename_guess(documents_root: Path) -> None:
    orphan = _write(documents_root / "old_older-report.pdf", PDF_BYTES, 1_600_000_000)
    newer = _write(documents_root / "new_new-brief.pdf", PDF_BYTES, 1_700_000_000)
    newer.with_suffix(".metadata.json").write_text(
        json.dumps(
            {
                "docId": "new_new-brief",
                "title": "Recorded Title",
                "createdAt": "2020-01-01T00:00:00+00:00",
                "pageCount": 9,
            }
        ),
        encoding="utf-8",
    )

    entries = inventory.list_document_artifacts()

    # The sidecar's recorded date outranks the file's mtime, so the indexed
    # document sorts last rather than inheriting a newer timestamp from disk.
    assert [entry["docId"] for entry in entries] == [orphan.stem, newer.stem]
    assert entries[0]["indexed"] is False
    assert entries[1]["indexed"] is True
    assert entries[1]["title"] == "Recorded Title"
    assert entries[1]["pageCount"] == 9


def test_kind_filter_matches_the_format_not_the_container(documents_root: Path) -> None:
    _write(documents_root / "a_one.pdf", PDF_BYTES, 1_700_000_000)
    _write(documents_root / "b_two.docx", PDF_BYTES, 1_700_000_001)

    assert [e["format"] for e in inventory.list_document_artifacts("pdf")] == ["pdf"]
    assert [e["format"] for e in inventory.list_document_artifacts("docx")] == ["docx"]
    assert len(inventory.list_document_artifacts("document")) == 2
    assert inventory.list_document_artifacts("image") == []


def test_unreadable_sidecar_degrades_to_the_file_itself(documents_root: Path) -> None:
    path = _write(documents_root / "x_broken.pdf", PDF_BYTES, 1_700_000_000)
    path.with_suffix(".metadata.json").write_text("{not json", encoding="utf-8")

    entry = inventory.list_document_artifacts()[0]

    assert entry["indexed"] is False
    assert entry["title"] == "Broken"


# ---------------------------------------------------------------------------
# Real request path
# ---------------------------------------------------------------------------


def test_generated_docs_endpoint_counts_orphans(
    client, documents_root: Path
) -> None:
    _write(documents_root / "solo_orphan-doc.pdf", PDF_BYTES, 1_700_000_000)

    payload = client.get("/api/v1/generated-docs").json()

    assert payload["count"] == 1
    assert payload["documents"][0]["indexed"] is False


def test_artifacts_endpoint_lists_documents_and_images(
    client, documents_root: Path, images_root: Path
) -> None:
    _write(documents_root / "solo_report.pdf", PDF_BYTES, 1_700_000_000)
    _write(images_root / "frame.png", PNG_BYTES, 1_800_000_000)

    payload = client.get("/api/v1/artifacts").json()

    assert payload["count"] == 2
    assert payload["documents"] == 1
    assert payload["images"] == 1
    # Newest across both stores, so the image leads.
    assert payload["artifacts"][0]["kind"] == "image"

    images_only = client.get("/api/v1/artifacts", params={"kind": "image"}).json()
    assert [item["kind"] for item in images_only["artifacts"]] == ["image"]


def test_lookup_returns_a_download_url_that_serves_the_file(
    client, documents_root: Path
) -> None:
    _write(documents_root / "solo_evidence.pdf", PDF_BYTES, 1_700_000_000)

    payload = client.get("/api/v1/artifacts/lookup", params={"kind": "pdf"}).json()

    assert payload["found"] is True
    assert payload["source"] == "documents"
    download = client.get(payload["downloadUrl"])
    assert download.status_code == 200
    assert download.content == PDF_BYTES


def test_lookup_for_an_absent_kind_answers_instead_of_erroring(
    client, documents_root: Path
) -> None:
    response = client.get("/api/v1/artifacts/lookup", params={"kind": "pptx"})

    assert response.status_code == 200
    assert response.json()["found"] is False


def test_generated_images_endpoint_keeps_its_row_shape(client, images_root: Path) -> None:
    _write(images_root / "frame.png", PNG_BYTES, 1_700_000_000)

    payload = client.get("/api/v1/generated-images").json()

    assert payload["count"] == 1
    row = payload["images"][0]
    assert row["filename"] == "frame.png"
    assert row["url"] == "/api/v1/generated-images/frame.png"
    assert set(row) >= {"id", "prompt", "created_at", "sizeKb"}


async def test_artifact_lookup_tool_finds_files_on_disk(documents_root: Path) -> None:
    _write(documents_root / "solo_deck.pdf", PDF_BYTES, 1_700_000_000)

    result = await artifact_lookup({"kind": "pdf"})

    assert result["found"] is True
    assert result["artifact"]["downloadUrl"] == "/api/v1/generated-docs/solo_deck"
    assert result["candidates"]


async def test_artifact_lookup_tool_no_longer_denies_that_images_exist(
    images_root: Path,
) -> None:
    _write(images_root / "frame.png", PNG_BYTES, 1_700_000_000)

    result = await artifact_lookup({"kind": "image"})

    assert result["found"] is True
    assert result["artifact"]["filename"] == "frame.png"


async def test_writer_records_the_sidecar_without_an_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hinaa_api.tools import document_generate
    from hinaa_api.tools.document_generate import GenerateDocumentParams

    monkeypatch.setattr(document_generate, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(inventory, "document_roots", lambda: [tmp_path])

    result = await document_generate.document_generate_handler(
        GenerateDocumentParams(title="Quarterly Note", content="Body text.", format="md")
    )

    assert result["status"] == "success"
    sidecars = list(tmp_path.glob("*.metadata.json"))
    assert len(sidecars) == 1, "an unowned write must still record its metadata"
    assert json.loads(sidecars[0].read_text(encoding="utf-8"))["ownerId"] == "unattributed"

    entry = inventory.list_document_artifacts()[0]
    assert entry["indexed"] is True
    assert entry["title"] == "Quarterly Note"
