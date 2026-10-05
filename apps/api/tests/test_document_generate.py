from __future__ import annotations

from pathlib import Path
import pytest

from hinaa_api.tools import document_generate, pdf_generate


@pytest.mark.asyncio
async def test_document_generator_docx_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(document_generate, "DOCS_DIR", tmp_path)
    result = await document_generate.document_generate_handler(
        document_generate.GenerateDocumentParams(
            topic="Quantum Computing and Shor Algorithm",
            content="# Quantum Foundations\n\nThese supplied notes are the source for this document export.",
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
    monkeypatch.setattr(pdf_generate, "DOCS_DIR", tmp_path)
    result = await document_generate.document_generate_handler(
        document_generate.GenerateDocumentParams(
            topic="World War II Causes",
            content="# Historical Notes\n\nThese supplied notes are the source for this PDF export.",
            format="pdf",
        )
    )

    assert result["status"] == "success"
    assert result["format"] == "pdf"
    assert result["downloadUrl"].startswith("/api/v1/generated-docs/")
