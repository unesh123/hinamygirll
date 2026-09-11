from __future__ import annotations

from pathlib import Path

import pytest

from hinaa_api.tools import pdf_generate


@pytest.mark.asyncio
async def test_pdf_generator_preserves_user_content_without_canned_research(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_render(*, doc_id: str, title: str, author: str, category: str, sections: list[tuple[str, object]]):
        captured.update(title=title, author=author, category=category, sections=sections)
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
    assert result["status"] == "success"
    assert result["pageCount"] == 1
    assert pdf_generate.pdf_generate_def.required_parameters == []
    assert "content" in pdf_generate.pdf_generate_def.parameters


@pytest.mark.asyncio
async def test_pdf_generator_topic_only_generates_academic_pdf(monkeypatch, tmp_path: Path) -> None:
    """Topic-only requests now generate academic content and return a downloadable PDF."""
    captured: dict[str, object] = {}

    def fake_render(*, doc_id: str, title: str, author: str, category: str, sections: list[tuple[str, object]]):
        captured.update(title=title, author=author, sections=sections)
        output = tmp_path / f"{doc_id}.pdf"
        output.write_bytes(b"%PDF-1.7 academic")
        return output, 3

    monkeypatch.setattr(pdf_generate, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(pdf_generate, "_generate_reportlab_pdf", fake_render)
    result = await pdf_generate.pdf_generate_handler(
        pdf_generate.GeneratePDFParams(topic="quantum computing")
    )
    assert result["status"] == "success"
    assert "docId" in result
    assert result["pageCount"] == 3
    assert captured["title"]  # title was derived from the topic
    assert len(captured["sections"]) > 0  # academic content was generated


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
