from __future__ import annotations

from pathlib import Path

import pytest

from hinaa_api.tools import pdf_generate


@pytest.mark.asyncio
async def test_pdf_generator_preserves_user_content_without_canned_research(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_render(*, doc_id: str, title: str, author: str, category: str, sections: list[tuple[str, object]], verification_note: str = ""):
        captured.update(title=title, author=author, category=category, sections=sections, note=verification_note)
        output = tmp_path / f"{doc_id}.pdf"
        output.write_bytes(b"%PDF-1.7 test")
        return output, 1

    monkeypatch.setattr(pdf_generate, "_generate_reportlab_pdf", fake_render)
    result = await pdf_generate.pdf_generate_handler(
        pdf_generate.GeneratePDFParams(
            title="My notes",
            category="Meeting notes",
            content="First paragraph supplied by the user.\n\nSecond paragraph with <literal> markup.",
            author="Unesh",
        )
    )

    assert captured["title"] == "My notes"
    sections = captured["sections"]
    assert isinstance(sections, list)
    rendered_text = "\n".join(str(section[1]) for section in sections)
    assert "First paragraph supplied by the user." in rendered_text
    assert "<literal>" in rendered_text
    assert "FlashAttention" not in rendered_text
    assert "supplied" in str(captured["note"]).lower()
    assert result["status"] == "success"
    assert result["pageCount"] == 1
    assert pdf_generate.pdf_generate_def.required_parameters == []
    assert "content" in pdf_generate.pdf_generate_def.parameters


@pytest.mark.asyncio
async def test_pdf_generator_topic_only_uses_live_research(monkeypatch, tmp_path: Path) -> None:
    """A bare topic yields a cited research dossier, or an honest refusal — never a template."""
    captured: dict[str, object] = {}

    def fake_render(*, doc_id: str, title: str, author: str, category: str, sections: list[tuple[str, object]], verification_note: str = ""):
        captured.update(title=title, author=author, sections=sections, note=verification_note)
        output = tmp_path / f"{doc_id}.pdf"
        output.write_bytes(b"%PDF-1.7 research")
        return output, 3

    async def answered(topic: str) -> list[tuple[str, object]]:
        return pdf_generate._research_sections(
            [{"source": "arxiv", "title": "Quantum error correction", "snippet": "Surface codes.", "url": "https://arxiv.org/abs/1"}],
            [{"id": "arxiv", "status": "ok", "count": 1}],
        )

    async def no_answer(topic: str) -> list[tuple[str, object]]:
        return []

    monkeypatch.setattr(pdf_generate, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(pdf_generate, "_generate_reportlab_pdf", fake_render)
    monkeypatch.setattr(pdf_generate, "_research_body", answered)
    result = await pdf_generate.pdf_generate_handler(
        pdf_generate.GeneratePDFParams(topic="quantum computing")
    )
    assert result["status"] == "success"
    assert "docId" in result
    assert result["pageCount"] == 3
    assert result["contentSource"] == "live-research"
    assert captured["title"]  # title derived from the topic
    assert len(captured["sections"]) > 0
    assert "https://arxiv.org/abs/1" in str(captured["sections"])

    monkeypatch.setattr(pdf_generate, "_research_body", no_answer)
    refused = await pdf_generate.pdf_generate_handler(
        pdf_generate.GeneratePDFParams(topic="quantum computing")
    )
    assert refused["status"] == "error"
    assert refused["code"] == "DOCUMENT_NO_SOURCE"


@pytest.mark.asyncio
async def test_pdf_generator_real_render_is_downloadable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pdf_generate, "DOCS_DIR", tmp_path)
    result = await pdf_generate.pdf_generate_handler(
        pdf_generate.GeneratePDFParams(
            title="Escaping test",
            content="<literal> & supplied text",
        )
    )
    output = tmp_path / f"{result['docId']}.pdf"
    assert result["status"] == "success"
    assert output.read_bytes().startswith(b"%PDF-")
    assert result["fileSizeBytes"] == output.stat().st_size
