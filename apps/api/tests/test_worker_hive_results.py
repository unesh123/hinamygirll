"""Mission results must reflect actual worker outputs, not a blanket success."""
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pypdf import PdfReader
from zipfile import ZipFile

from hinaa_api.agents.worker_hive import WorkerHive
from hinaa_api.tools import document_generate, image_generate, pdf_generate


@pytest.fixture
def research(monkeypatch):
    worker = AsyncMock(return_value=[("Study plan", "Study algebra on Monday. Review notes on Tuesday.")])
    monkeypatch.setattr(pdf_generate, "_research_body", worker)
    return worker


@pytest.mark.asyncio
async def test_documents_use_current_handlers_and_produce_valid_files(tmp_path, monkeypatch, research):
    monkeypatch.setattr(pdf_generate, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(document_generate, "DOCS_DIR", tmp_path)
    result = await WorkerHive().execute_mission("Study plan", tasks=["pdf", "pptx"])
    assert result["status"] == "success", result
    assert set(result["deliverables"]) == {"pdf", "pptx"}
    for fmt in ("pdf", "pptx"):
        artifact = result["deliverables"][fmt]
        assert artifact["validationStatus"] == "validated"
        assert artifact["downloadUrl"].startswith("/api/v1/generated-docs/")
        path = Path(artifact["canonicalPath"])
        assert path.is_file()
        if fmt == "pdf":
            assert "Monday" in " ".join(p.extract_text() for p in PdfReader(path).pages)
        else:
            with ZipFile(path) as archive:
                assert "ppt/presentation.xml" in archive.namelist()
    research.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_research_does_not_invent_completed_work(research):
    research.return_value = []
    result = await WorkerHive().execute_mission("Study plan", tasks=["research", "pdf"])
    assert result["status"] == "error"
    assert result["deliverables"] == {}
    assert set(result["errors"]) == {"research", "pdf"}


@pytest.mark.asyncio
async def test_processing_images_are_not_completed_artifacts(monkeypatch, research):
    image = AsyncMock(return_value={"status": "processing", "job_id": "job-1"})
    monkeypatch.setattr(image_generate, "image_generate_handler", image)
    result = await WorkerHive().execute_mission("Study plan", tasks=["creative"])
    assert result["status"] == "processing"
    assert result["deliverables"] == {}
    assert result["pending"]["creative"]["job_id"] == "job-1"
    research.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_document_remains_partial_without_success_card(monkeypatch, research):
    monkeypatch.setattr(document_generate, "document_generate_handler", AsyncMock(side_effect=RuntimeError("worker failed")))
    result = await WorkerHive().execute_mission("Study plan", tasks=["research", "pdf"])
    assert result["status"] == "partial"
    assert set(result["deliverables"]) == {"research"}
    assert "pdf" in result["errors"]


@pytest.mark.asyncio
async def test_unvalidated_output_is_not_a_deliverable(monkeypatch, research):
    monkeypatch.setattr(document_generate, "document_generate_handler", AsyncMock(return_value={
        "status": "success", "downloadUrl": "/missing.pdf",
    }))
    result = await WorkerHive().execute_mission("Study plan", tasks=["pdf"])
    assert result["status"] == "error"
    assert result["deliverables"] == {}


@pytest.mark.asyncio
async def test_unknown_or_empty_tasks_do_not_run_paid_workers(research):
    for tasks in ([], ["unknown"]):
        result = await WorkerHive().execute_mission("Study plan", tasks=tasks)
        assert result["status"] == "error"
    research.assert_not_awaited()
