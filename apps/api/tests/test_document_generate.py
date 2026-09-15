from __future__ import annotations

from pathlib import Path
import pytest

from hinaa_api.tools import document_generate


@pytest.mark.asyncio
async def test_document_generator_docx_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(document_generate, "DOCS_DIR", tmp_path)
    result = await document_generate.document_generate_handler(
        document_generate.GenerateDocumentParams(
            topic="Quantum Computing and Shor Algorithm",
            title="Quantum Foundations",
            format="docx",
        )
    )

    assert result["status"] == "success"
    assert result["format"] == "docx"
    assert result["downloadUrl"].startswith("/api/v1/generated-docs/")
    assert result["fileSizeBytes"] > 1000
    doc_file = tmp_path / f"{result['docId']}_{result['filename']}"
    assert doc_file.exists()


@pytest.mark.asyncio
async def test_document_generator_pdf_delegation(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(document_generate, "DOCS_DIR", tmp_path)
    result = await document_generate.document_generate_handler(
        document_generate.GenerateDocumentParams(
            topic="World War II Causes",
            format="pdf",
        )
    )

    assert result["status"] == "success"
    assert result["format"] == "pdf"
    assert result["downloadUrl"].startswith("/api/v1/generated-docs/")
