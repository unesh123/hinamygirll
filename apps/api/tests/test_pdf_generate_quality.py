from __future__ import annotations

from pathlib import Path
import pytest

from hinaa_api.tools import pdf_generate
from hinaa_api.config import Settings
from hinaa_api.models import TurnRequest
from hinaa_api.services import ConversationService


def test_markdown_parser_headings_bullets_and_tables():
    markdown = """# Executive Overview
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
    sections = pdf_generate._build_user_content_sections(markdown)
    assert len(sections) >= 3
    
    titles = [s[0] for s in sections]
    assert "Executive Overview" in titles
    assert "Key Observations" in titles
    assert "Benchmark Data" in titles
    assert "Strategic Recommendations" in titles

    table_section = next(s for s in sections if s[0] == "Benchmark Data")
    elements = table_section[1]
    assert isinstance(elements, list)
    # The table is parsed into a 2D list of row cells: list[list[str]]
    has_table = any(isinstance(el, list) and len(el) > 0 and isinstance(el[0], list) for el in elements)
    assert has_table, "Benchmark Data section should contain parsed table data rows"


def test_domain_specific_academic_generators_no_boilerplate():
    boilerplate = "This academic study investigates the fundamental dynamics"

    # 1. History
    h_title, history_sections = pdf_generate._build_academic_content("World War II causes and major turning points")
    h_text = " ".join(str(s[1]) for s in history_sections)
    assert boilerplate not in h_text
    assert "Treaty of Versailles" in h_text or "Axis" in h_text or "Battle of Midway" in h_text
    assert any("Historiographical" in s[0] or "Scholarly" in s[0] or "References" in s[0] or "Citations" in s[0] for s in history_sections)

    # 2. Biology
    b_title, bio_sections = pdf_generate._build_academic_content("CRISPR-Cas9 gene editing and molecular biology")
    b_text = " ".join(str(s[1]) for s in bio_sections)
    assert boilerplate not in b_text
    assert "macromolecular" in b_text.lower() or "dna" in b_text.lower() or "crispr" in b_text.lower()
    assert any("Citations" in s[0] or "References" in s[0] for s in bio_sections)

    # 3. Economics
    e_title, econ_sections = pdf_generate._build_academic_content("Macroeconomic inflation and monetary policy")
    e_text = " ".join(str(s[1]) for s in econ_sections)
    assert boilerplate not in e_text
    assert "monetary" in e_text.lower() or "inflation" in e_text.lower() or "equilibrium" in e_text.lower()
    assert any("References" in s[0] or "Econometric" in s[0] or "Citations" in s[0] for s in econ_sections)

    # 4. Computer Science / AI
    cs_title, cs_sections = pdf_generate._build_academic_content("Deep neural network architectures and transformers")
    cs_text = " ".join(str(s[1]) for s in cs_sections)
    assert boilerplate not in cs_text
    assert "transformer" in cs_text.lower() or "flashattention" in cs_text.lower() or "complexity" in cs_text.lower()
    assert any("Citations" in s[0] or "References" in s[0] for s in cs_sections)

    # 5. Universal Academic
    u_title, univ_sections = pdf_generate._build_academic_content("Astrophysical accretion disks around Kerr black holes")
    u_text = " ".join(str(s[1]) for s in univ_sections)
    assert boilerplate not in u_text
    assert len(univ_sections) >= 6
    assert any("References" in s[0] or "Bibliography" in s[0] or "Citations" in s[0] for s in univ_sections)


@pytest.mark.asyncio
async def test_academic_pdf_real_render_multi_page(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(pdf_generate, "DOCS_DIR", tmp_path)
    
    result = await pdf_generate.pdf_generate_handler(
        pdf_generate.GeneratePDFParams(
            topic="World War II causes and major turning points",
            author="Hinaa Research Division",
        )
    )
    assert result["status"] == "success"
    assert result["pageCount"] >= 2, f"Expected multi-page PDF, got {result['pageCount']}"
    assert result["fileSizeBytes"] > 5000, f"Expected rich PDF > 5KB, got {result['fileSizeBytes']}"
    
    pdf_file = tmp_path / f"{result['docId']}.pdf"
    assert pdf_file.exists()
    assert pdf_file.read_bytes().startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_anaphora_resolution_extracts_previous_topic():
    settings = Settings(provider_mode="mock")
    service = ConversationService(settings)
    session_id = "test-session-anaphora"
    
    # User had a prior discussion about World War II
    service.memory.append_turn(
        session_id,
        "Tell me about the causes of World War II and the major alliances.",
        '{"displayText": "# World War II Analysis\n\nThe conflict arose from the Treaty of Versailles and expansionist fascism.\n\n## Major Alliances\n- Allied Powers: UK, USSR, USA\n- Axis Powers: Germany, Japan, Italy", "spokenText": "Here is the summary of World War II babe."}'
    )
    
    # User now asks for a PDF based on the assignment
    req = TurnRequest(
        sessionId=session_id,
        userId="user-1",
        text="can you make a pdf based on that assignment",
    )
    plan = await service.create_plan(req)
    
    # Verify toolRequest for pdf_generate was generated
    assert plan.value.toolRequests is not None and len(plan.value.toolRequests) > 0
    tool_req = plan.value.toolRequests[0]
    assert tool_req.toolName == "pdf_generate"
    
    # Topic should NOT be 'based on that' or 'that assignment', it should be resolved from context
    resolved_topic = tool_req.parameters.get("topic", "")
    assert "world war" in resolved_topic.lower() or "causes" in resolved_topic.lower()
    
    # Substantive content should be passed
    content = tool_req.parameters.get("content", "")
    assert len(content) > 20
    assert "World War II Analysis" in content or "Allied Powers" in content
