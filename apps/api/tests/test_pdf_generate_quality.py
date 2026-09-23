"""Document-body provenance: Hina may typeset real material or refuse, never invent.

These tests pin the contract that replaced the canned academic builders: the body
comes from supplied text or a live research pass, every finding carries its own
address, and an empty pass yields an error instead of a filled-in template.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from hinaa_api.tools import pdf_generate
from hinaa_api.config import Settings
from hinaa_api import services
from hinaa_api.models import AssistantTurnPlan, TurnRequest
from hinaa_api.services import ConversationService


SUPPLIED_MARKDOWN = """# Executive Overview
This document synthesizes key findings from empirical analysis.

## Key Observations
- Primary observation on throughput metrics.
- Secondary observation regarding latency bounds.
* Tertiary note on algorithmic convergence.

### Benchmark Data
| Metric | Baseline | Optimized | Delta |
| Latency | 45ms | 12ms | -73% |
| Memory | 1.2GB | 410MB | -65% |
| Accuracy | 91.2% | 94.8% | +3.6% |

## Strategic Recommendations
1. Deploy speculative decoding on edge clusters.
2. Maintain zero-trust token authentication.
"""


def test_markdown_parser_headings_bullets_and_tables():
    sections = pdf_generate._build_user_content_sections(SUPPLIED_MARKDOWN)
    assert len(sections) >= 3

    titles = [s[0] for s in sections]
    assert "Executive Overview" in titles
    assert "Key Observations" in titles
    assert "Benchmark Data" in titles
    assert "Strategic Recommendations" in titles

    table_section = next(s for s in sections if s[0] == "Benchmark Data")
    elements = table_section[1]
    assert isinstance(elements, list)
    has_table = any(isinstance(el, list) and len(el) > 0 and isinstance(el[0], list) for el in elements)
    assert has_table, "Benchmark Data section should contain parsed table data rows"


def test_inventing_builders_are_gone():
    for name in (
        "_build_academic_content",
        "_build_universal_academic_content",
        "_build_history_content",
        "_build_biology_content",
        "_build_economics_content",
        "_build_cs_ai_content",
    ):
        assert not hasattr(pdf_generate, name), f"{name} could still fabricate a document"


def test_tool_descriptions_do_not_promise_invented_content():
    from hinaa_api.tools.document_generate import document_generate_def
    from hinaa_api.tools.pdf_generate import pdf_generate_def

    for definition in (pdf_generate_def, document_generate_def):
        text = definition.description + " ".join(
            str(spec.get("description", "")) for spec in definition.parameters.values()
        )
        assert "DOCUMENT_NO_SOURCE" in text, f"{definition.name} must advertise that it refuses"
        assert "generate research" not in text.lower()


def test_supplied_text_is_the_body_and_keeps_a_document_register():
    title, sections, provenance = _run(
        pdf_generate.compose_document_source(
            topic="World War II causes",
            content="Hey babe, here is my assignment on the Weimar Republic.\n\nThe Treaty of Versailles imposed reparations.",
            title=None,
        )
    )
    assert provenance == "supplied-text"
    body = " ".join(str(block) for _, blocks in sections for block in _flat(blocks))
    assert "Treaty of Versailles" in body
    assert not re.search(r"(?i)\bbabe\b", body), "chat warmth leaked into the document"


def test_bare_topic_refuses_instead_of_filling_template(monkeypatch):
    async def no_answer(topic: str) -> list:
        return []

    monkeypatch.setattr(pdf_generate, "_research_body", no_answer)
    with pytest.raises(pdf_generate.NoDocumentSource):
        _run(pdf_generate.compose_document_source(topic="Astrophysics", content=None, title=None))


def test_handler_reports_refusal_and_writes_no_file(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pdf_generate, "DOCS_DIR", tmp_path)

    async def no_answer(topic: str) -> list:
        return []

    monkeypatch.setattr(pdf_generate, "_research_body", no_answer)
    result = _run(
        pdf_generate.pdf_generate_handler(pdf_generate.GeneratePDFParams(topic="Cryptography history"))
    )
    assert result["status"] == "error"
    assert result["code"] == "DOCUMENT_NO_SOURCE"
    assert list(tmp_path.iterdir()) == [], "a refused document must not leave a file behind"


def test_research_sections_cite_every_finding():
    items = [
        {"source": "wikipedia", "title": "Naval Enigma", "snippet": "Machines used by Kriegsmarine.", "url": "https://example.org/enigma"},
        {"source": "arxiv", "title": "Cryptanalysis survey", "snippet": "", "url": "https://arxiv.org/abs/1234"},
    ]
    sources = [
        {"id": "wikipedia", "status": "ok", "count": 1},
        {"id": "arxiv", "status": "ok", "count": 1},
        {"id": "hackernews", "status": "failed", "count": 0, "error": "timed out"},
    ]
    sections = pdf_generate._research_sections(items, sources)
    titles = [heading for heading, _ in sections]
    assert "Sources queried" in titles
    body = " ".join(str(block) for _, blocks in sections for block in _flat(blocks))
    assert "https://example.org/enigma" in body
    assert "https://arxiv.org/abs/1234" in body
    assert "timed out" in body, "a source that did not answer must be named, not hidden"


def test_live_research_pdf_is_stamped_with_its_provenance(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pdf_generate, "DOCS_DIR", tmp_path)

    async def answered(topic: str) -> list:
        return pdf_generate._research_sections(
            [{"source": "wikipedia", "title": "Enigma", "snippet": "Cipher machine.", "url": "https://example.org/e"}],
            [{"id": "wikipedia", "status": "ok", "count": 1}],
        )

    monkeypatch.setattr(pdf_generate, "_research_body", answered)
    result = _run(
        pdf_generate.pdf_generate_handler(
            pdf_generate.GeneratePDFParams(topic="Enigma cipher machines", author="Unesh")
        )
    )
    assert result["status"] == "success", result
    assert result["contentSource"] == "live-research"
    assert "example.org" in result["summary"] or result["sectionCount"] >= 2

    pdf_file = tmp_path / f"{result['docId']}.pdf"
    assert pdf_file.exists()
    assert pdf_file.read_bytes().startswith(b"%PDF-")


def test_supplied_text_pdf_renders_without_the_network(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pdf_generate, "DOCS_DIR", tmp_path)

    async def should_not_run(topic: str) -> list:  # pragma: no cover - guards the network
        raise AssertionError("supplied content must not trigger a research pass")

    monkeypatch.setattr(pdf_generate, "_research_body", should_not_run)
    result = _run(
        pdf_generate.pdf_generate_handler(
            pdf_generate.GeneratePDFParams(
                topic="Throughput study",
                title="Throughput Study",
                content=SUPPLIED_MARKDOWN,
            )
        )
    )
    assert result["status"] == "success"
    assert result["contentSource"] == "supplied-text"
    assert result["pageCount"] >= 1
    assert result["fileSizeBytes"] > 2000
    assert (tmp_path / f"{result['docId']}.pdf").read_bytes().startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_anaphora_resolution_extracts_previous_topic():
    settings = Settings(provider_mode="mock")
    service = ConversationService(settings)
    session_id = "test-session-anaphora"

    service.memory.append_turn(
        session_id,
        "Tell me about the causes of World War II and the major alliances.",
        '{"displayText": "# World War II Analysis\\n\\nThe conflict arose from the Treaty of Versailles and expansionist fascism.\\n\\n## Major Alliances\\n- Allied Powers: UK, USSR, USA\\n- Axis Powers: Germany, Japan, Italy", "spokenText": "Here is the summary of World War II babe."}',
    )

    req = TurnRequest(
        sessionId=session_id,
        userId="user-1",
        text="can you make a pdf based on that assignment",
    )
    plan = await service.create_plan(req)

    assert plan.value.toolRequests is not None and len(plan.value.toolRequests) > 0
    tool_req = plan.value.toolRequests[0]
    assert tool_req.toolName == "pdf_generate"

    resolved_topic = tool_req.parameters.get("topic", "")
    assert "world war" in resolved_topic.lower() or "causes" in resolved_topic.lower()

    content = tool_req.parameters.get("content", "")
    assert len(content) > 20
    assert "World War II Analysis" in content or "Allied Powers" in content


def test_pdf_trigger_does_not_claim_content_it_did_not_write():
    """The turn may not promise analysis or citations the builder cannot guarantee."""
    settings = Settings(provider_mode="mock")
    service = ConversationService(settings)
    plan = _run(
        service.create_plan(
            TurnRequest(sessionId="s-pdf-claim", userId="user-1", text="make me a pdf about photosynthesis")
        )
    ).value

    text = plan.displayText + " " + plan.spokenText
    assert not re.search(r"(?i)\b(?:with|and)\s+(?:detailed\s+analysis|citations|references|comparison tables)\b", text), text
    assert re.search(r"(?i)typesetting|lays? .{0,20}out", plan.displayText), plan.displayText


FABRICATED_SUMMARY = (
    "I have compiled your complete academic assignment and research report on "
    "**Quantum Computing** into a publication-grade PDF with structured foundations, "
    "comparison tables, detailed analysis, and citations."
)


def _plan_with_pending_document_tool() -> AssistantTurnPlan:
    service = ConversationService(Settings(provider_mode="mock"))
    plan = _run(
        service.create_plan(
            TurnRequest(sessionId="s-pdf-guard", userId="user-1", text="make me a pdf about quantum computing")
        )
    ).value
    assert [t.toolName for t in plan.toolRequests] == ["pdf_generate"], plan.toolRequests
    return plan


@pytest.mark.parametrize("tool_name", ["pdf_generate", "document_generate"])
def test_pending_document_turn_strips_claims_about_the_file(tool_name: str):
    """Nothing exists yet at guard time, so the reply may not describe the file's contents."""
    plan = _plan_with_pending_document_tool()
    plan.toolRequests[0].toolName = tool_name
    plan.displayText = plan.spokenText = FABRICATED_SUMMARY
    services._apply_response_quality_guard(plan)

    for field in (plan.displayText, plan.spokenText):
        assert "comparison tables" not in field, field
        assert "detailed analysis" not in field, field
        assert "citations" not in field, field
    assert "publication-grade PDF" in plan.displayText, plan.displayText
    assert plan.toolRequests[0].parameters.get("topic") == "quantum computing"


def test_the_shield_does_not_widen_past_documents():
    """Ordinary prose keeps its wording; only document turns are scrubbed."""
    plan = _plan_with_pending_document_tool()
    plan.toolRequests[0].toolName = "web_search"
    plan.displayText = plan.spokenText = FABRICATED_SUMMARY
    services._apply_response_quality_guard(plan)
    assert "comparison tables" in plan.displayText, plan.displayText

    honest = _plan_with_pending_document_tool()
    honest.spokenText = honest.displayText = (
        "• **Layout**: ReportLab PDF with running header and page numbers\n\n"
        "The document builder only lays that material out - it does not add sections, facts, or references of its own."
    )
    services._apply_response_quality_guard(honest)
    assert "running header and page numbers" in honest.displayText, honest.displayText
    assert "references of its own" in honest.displayText, honest.displayText


def _flat(block):
    for item in block if isinstance(block, list) else [block]:
        if isinstance(item, list):
            yield from _flat(item)
        else:
            yield item


def _run(coroutine):
    import asyncio

    return asyncio.run(coroutine)
