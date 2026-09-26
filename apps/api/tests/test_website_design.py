"""A website ask has to produce a page that renders, and a URL that shows it.

The two ways a page gets its words are his own copy and a live research pass, so
both are covered here against a stubbed pass; the refusal that fires when neither
answers is the row that keeps a template full of invented features from shipping.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from hinaa_api.models import ToolRequest
from hinaa_api.tools import deep_research, website_design
from hinaa_api.tools.intent_gate import (
    blocked_note,
    gate_tool_requests,
    page_will_be_built,
    sanction_tools,
)

COPY = """# Kathmandu Roasters

We roast in small batches every Tuesday in Thamel &amp; ship&nbsp;worldwide.

## What we sell
- Single origin Palung — washed, citrus and honey, 250g for Rs 950
- Chiwatung lot 4 — anaerobic, stone fruit, 1kg for Rs 3200
- Blend No. 7 — chocolate, walnut, house espresso <script>alert('xss')</script>

## Tasting notes
| Coffee | Process | Score |
| --- | --- | --- |
| Palung | Washed | 87 |
| Chiwatung | Anaerobic | 88.5 |

Visit https://example.com/roastery for the full list.
"""

REPEATED = "Best Treks in Nepal for 2026: A Practical Guide"
TRUNCATED = "Permit rules change for the Annapurna circuit this season again"
LATER = "Season dates for the Manaslu circuit"
EXTRA = "Where to rent gear in Thamel"

FINDINGS = {
    "status": "success",
    "data": {
        "items": [
            # Both of these repeat their own headline back, one in each direction.
            {"title": REPEATED, "snippet": REPEATED, "url": "https://one.example/guide", "source": "web"},
            {"title": TRUNCATED, "snippet": TRUNCATED[:40], "url": "https://two.example/permits", "source": "web"},
            {"title": "Route closed over Kathma Danda pass", "snippet": "Closure lasts to the end of monsoon.",
             "url": "https://three.example/pass", "source": "web"},
            {"title": "New teahouse standards published", "snippet": "Insurance is now mandatory for porters.",
             "url": "https://four.example/teahouse", "source": "news"},
            {"title": "Airport upgrade at Lukla", "snippet": "Resurfacing finishes before the autumn season.",
             "url": "https://five.example/lukla", "source": "news"},
            {"title": "Guide licensing counts", "snippet": "Registered guides crossed twelve thousand.",
             "url": "https://six.example/guides", "source": "news"},
            {"title": LATER, "snippet": "Permits open in two windows each year.",
             "url": "https://seven.example/manaslu", "source": "news"},
            {"title": EXTRA, "snippet": "Deposit-free hire at four shops.",
             "url": "https://eight.example/gear", "source": "news"},
        ],
        "sources": ["one.example"],
    },
}


async def _fake_research(params):
    return FINDINGS


@pytest.fixture
def isolated_docs(tmp_path, monkeypatch):
    """Write pages to a temp store and point the file route at the same place."""
    monkeypatch.setattr(website_design, "DOCS_DIR", tmp_path)
    monkeypatch.setattr("hinaa_api.artifacts.inventory.document_roots", lambda: [tmp_path])
    return tmp_path


def _page(isolated_docs, result) -> str:
    return (Path(isolated_docs) / f"{result['docId']}_{result['filename']}").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_supplied_copy_is_laid_out_and_never_executes(isolated_docs):
    result = await website_design.website_design_handler(
        website_design.DesignWebsiteParams(userId="owner", title="Kathmandu Roasters", content=COPY)
    )

    assert result["status"] == "success"
    assert result["contentSource"] == "supplied-text"
    assert result["fileSizeBytes"] > 2000
    markup = _page(isolated_docs, result)

    # Nothing he pasted may run, and an entity must not survive as its own name.
    assert "<script" not in markup.casefold()
    assert "alert(&#x27;xss&#x27;)" in markup
    assert "&amp;nbsp;" not in markup and "&amp;amp;" not in markup
    assert "Thamel &amp; ship worldwide" in markup
    assert "Rs 950" in markup and "88.5" in markup
    assert 'href="https://example.com/roastery"' in markup
    assert result["highlightCount"] == 3
    assert "Tasting notes" in result["sections"]

    sidecar = json.loads((Path(isolated_docs) / f"{result['docId']}_{result['filename']}").with_suffix(".site.json").read_text(encoding="utf-8"))
    assert sidecar["ownerId"] == "owner"
    assert "<style>" not in json.dumps(sidecar)


@pytest.mark.asyncio
async def test_research_findings_are_promoted_once_not_printed_twice(isolated_docs, monkeypatch):
    monkeypatch.setattr(deep_research, "deep_research_handler", _fake_research)
    result = await website_design.website_design_handler(
        website_design.DesignWebsiteParams(userId="owner", brief="trekking in Nepal")
    )

    assert result["status"] == "success"
    assert result["contentSource"] == "live-research"
    assert result["highlightCount"] == website_design.MAX_CARDS
    assert result["linkCount"] == len(FINDINGS["data"]["items"])
    # Only the findings that were not promoted to a card keep their own section.
    assert result["sections"] == ["News findings"]

    body = _page(isolated_docs, result).split("<body", 1)[1]
    assert f"{REPEATED} —" not in body and f"— {REPEATED}" not in body
    assert "— </li>" not in body
    assert LATER in body and EXTRA in body


@pytest.mark.asyncio
async def test_a_page_that_is_only_highlights_still_ships(isolated_docs):
    list_only = "\n".join([
        "# Services",
        "",
        "- Roof repair — slate, flat and metal, ten year workmanship warranty",
        "- Gutter clearing — same week booking across the valley",
        "- Waterproofing — membrane and injection with a written report",
    ])
    result = await website_design.website_design_handler(
        website_design.DesignWebsiteParams(userId="owner", title="Services", content=list_only)
    )

    assert result["status"] == "success"
    assert result["highlightCount"] == 3
    assert result["sections"] == []
    assert "Roof repair" in _page(isolated_docs, result)


@pytest.mark.asyncio
async def test_no_source_refuses_instead_of_inventing_copy(isolated_docs, monkeypatch):
    async def dead(params):
        raise RuntimeError("every research provider is down")

    monkeypatch.setattr(deep_research, "deep_research_handler", dead)
    result = await website_design.website_design_handler(
        website_design.DesignWebsiteParams(userId="owner", brief="a site for my bakery")
    )

    assert result["status"] == "error"
    assert result["code"] == "WEBSITE_NO_SOURCE"
    assert "invented" in result["error"]
    assert list(Path(isolated_docs).glob("*.html")) == []


def test_the_gate_reads_a_website_out_of_his_words():
    for text in (
        "design a landing page with a hero image for my coffee roastery",
        "build me a website for Kathmandu Roasters",
        "can you make a site for the hostel?",
        "/site Kathmandu Roasters one page with the menu",
    ):
        assert sanction_tools(text).allowed == {"design_website"}, text

    for text in (
        "generate a image of a cat",
        "draw hina sitting in a cafe",
        "make me a pdf about world war 2",
        "why is the website broken",
        "search the web for the latest episode",
    ):
        assert "design_website" not in sanction_tools(text).allowed, text


def test_the_stream_knows_a_page_is_coming_before_the_brain_speaks():
    """``page_will_be_built`` gates the live wire, so it has to agree with the
    sanction that files the call -- and stay quiet on a question about markup."""
    for text in (
        "design a landing page with a hero image for my coffee roastery",
        "build me a website for Kathmandu Roasters",
        "/site Kathmandu Roasters one page with the menu",
    ):
        assert page_will_be_built(text) is True, text

    for text in (
        "why is the website broken",
        "show me what an html table looks like",
        "what does <!DOCTYPE html> do",
        "how are you today",
    ):
        assert page_will_be_built(text) is False, text


def test_an_invented_website_call_is_refused_in_plain_words():
    planned = [ToolRequest(toolName="design_website", parameters={"brief": "something"})]

    kept, dropped, _ = gate_tool_requests("build me a website for the clinic", planned)
    assert [req.toolName for req in kept] == ["design_website"]
    assert dropped == []

    kept, dropped, _ = gate_tool_requests("how are you today", planned)
    assert kept == []
    assert blocked_note(dropped) == (
        "I did not build a website because your message was not a request for one."
    )


def test_the_gate_files_the_page_when_the_answering_brain_planned_nothing():
    """Measured on the streamed turn: the sanction named the tool, the weak brain
    filed no call, and the bubble described a site nobody built."""
    kept, dropped, _ = gate_tool_requests(
        "build me a one page website for Himalayan Java Roasters in Jhamsikhel", []
    )

    assert dropped == []
    assert [req.toolName for req in kept] == ["design_website"]
    assert kept[0].parameters["brief"] == (
        "build me a one page website for Himalayan Java Roasters in Jhamsikhel"
    )


@pytest.mark.asyncio
async def test_the_command_never_became_the_page_name(isolated_docs, monkeypatch):
    monkeypatch.setattr(deep_research, "deep_research_handler", _fake_research)
    result = await website_design.website_design_handler(
        website_design.DesignWebsiteParams(
            userId="owner",
            brief="build me a one page website for Himalayan Java Roasters in Jhamsikhel",
        )
    )

    assert result["status"] == "success"
    assert result["title"] == "Himalayan Java Roasters in Jhamsikhel"
    body = _page(isolated_docs, result)
    assert "<h1 class=\"rise\">Himalayan Java Roasters in Jhamsikhel</h1>" in body
    assert "build me a one page website" not in body


def test_a_slash_command_keeps_the_arguments_he_typed_after_it():
    image = [ToolRequest(toolName="image_generate", parameters={"prompt": "a red fox", "count": 1})]
    kept, dropped, _ = gate_tool_requests("/image a red fox", image)
    assert dropped == []
    assert kept[0].parameters["prompt"] == "Red fox"

    site = [ToolRequest(toolName="design_website", parameters={"brief": "Kathmandu Roasters one page"})]
    kept, dropped, sanction = gate_tool_requests("/site Kathmandu Roasters one page", site)
    assert dropped == []
    assert kept[0].parameters["brief"] == "Kathmandu Roasters one page"
    assert sanction.explicit is True


def test_preview_route_sends_the_page_inline_not_as_a_file(isolated_docs, client, monkeypatch):
    monkeypatch.setattr(deep_research, "deep_research_handler", _fake_research)
    result = asyncio.run(
        website_design.website_design_handler(
            website_design.DesignWebsiteParams(userId="owner", brief="trekking in Nepal")
        )
    )
    assert result["status"] == "success"

    preview = client.get(result["previewUrl"])
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith("text/html")
    assert "<!DOCTYPE html>" in preview.text
    # The page carries no scripts by construction; the headers make that a guarantee
    # rather than a habit, and an opaque origin so it cannot reach this one back.
    assert preview.headers["content-security-policy"] == (
        "sandbox; default-src 'none'; style-src 'unsafe-inline'"
    )
    assert preview.headers["x-content-type-options"] == "nosniff"
    assert "content-disposition" not in preview.headers

    download = client.get(result["downloadUrl"])
    assert download.status_code == 200
    assert download.headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize(
    "doc_id",
    [
        "not-a-uuid",
        "..\\..\\etc\\passwd",
        "00000000-0000-0000-0000-000000000000",
        "a" * 35 + "*",  # 36 characters, but a glob metacharacter may not widen the search
    ],
)
def test_preview_route_answers_404_for_anything_it_did_not_build(isolated_docs, client, doc_id):
    (Path(isolated_docs) / f"{'a' * 35}_x.html").write_text("<h1>ours, but not that id</h1>", encoding="utf-8")
    assert client.get(f"/api/v1/generated-docs/{doc_id}/preview").status_code == 404
