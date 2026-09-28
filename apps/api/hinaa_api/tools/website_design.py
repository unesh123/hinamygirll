"""website_design.py — lay out a whole page, and answer a URL that shows it live.

A website ask is different from a document ask: the layout is the deliverable, so
it can be composed from his words without inventing anything. The copy inside it
cannot. So the body comes either from text he supplied or from the live research
pass, and when neither answers the tool refuses instead of shipping a template
page full of "Lorem ipsum" and made-up prices.

The page carries no JavaScript at all. Every interaction is CSS — which is what
lets the preview route hand it out under ``Content-Security-Policy: sandbox``
without the opaque origin costing anything.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field

from hinaa_api.tools.pdf_generate import (
    DOCS_DIR,
    _build_user_content_sections,
    _sanitize_slug,
    _scrub_chat_affection,
)
from hinaa_api.tools.registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.website_design")

MAX_CARDS = 6
MAX_TEXT_LINKS = 12
CARD_BODY_LIMIT = 180

_ACCENT = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_URL = re.compile(r"https?://[^\s)\]}<>\"']+")

# Chosen by subject hash, so the same brief keeps the same skin and a new one
# gets a new look without the layout engine picking at random between runs.
PALETTES: tuple[tuple[str, str, str], ...] = (
    ("#4338ca", "#0d9488", "#f6f7fb"),
    ("#b45309", "#7c2d12", "#fbf7f2"),
    ("#0f766e", "#1e3a8a", "#f2f7f7"),
    ("#9d174d", "#4c1d95", "#fbf3f7"),
    ("#1d4ed8", "#0369a1", "#f3f6fc"),
    ("#15803d", "#166534", "#f4faf5"),
)


class DesignWebsiteParams(BaseModel):
    model_config = {"extra": "ignore"}

    userId: str | None = None
    brief: str | None = Field(None, max_length=20_000, description="What the site is for, in his words")
    title: str | None = Field(None, max_length=300, description="Name shown in the page header")
    content: str | None = Field("", max_length=150_000, description="Copy to lay out verbatim")
    subject: str | None = Field(None, max_length=2_000, description="Alias for the research subject")
    query: str | None = Field(None, max_length=2_000, description="Alias for the research subject")
    prompt: str | None = Field(None, max_length=2_000, description="Alias for the research subject")
    topic: str | None = Field(None, max_length=2_000, description="Alias for the research subject")
    accent: str | None = Field(None, max_length=7, description="Brand colour as #hex")
    theme: Literal["light", "dark", "auto"] = "auto"


@dataclass
class Block:
    heading: str
    anchor: str
    lead: str = ""
    bullets: list[str] = field(default_factory=list)
    table: list[list[str]] = field(default_factory=list)


@dataclass
class SitePlan:
    title: str
    eyebrow: str
    tagline: str
    accent: str
    accent_2: str
    on_accent: str
    surface: str
    theme: str
    cards: list[tuple[str, str]] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)
    provenance: str = "supplied-text"


# Emphasis and block markers from the source's own markdown. The page renders
# plain text, so the scaffolding reads as noise while the words stay.
_MARKDOWN_NOISE = re.compile(r"^[#>\-*]+\s+|\*\*|__|~~|`")


def _text(value: Any) -> str:
    """One plain line of text, entities and markup scaffolding resolved.

    Decoding is safe because every value that reaches the page goes back out
    through ``_esc``, which escapes what it turns into.
    """
    cleaned = _MARKDOWN_NOISE.sub(" ", html.unescape(str(value or "")))
    return re.sub(r"\s+", " ", cleaned).strip()


def _trimmed(value: Any, limit: int) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return (cut[: cut.rfind(" ")] if " " in cut else cut).rstrip(",;:") + "…"


def _esc(value: Any) -> str:
    return html.escape(_text(value), quote=True)


def _anchor_for(heading: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", heading.casefold()).strip("-")
    return (slug or f"section-{index + 1}")[:48]


# The gate hands this module his own sentence, and the first words of that
# sentence are the request, not the subject: printing "build me a one page
# website for X" as the page title puts his keystrokes on the page instead of
# what they were about.
_SITE_REQUEST = re.compile(
    r"""(?ix)^\s*(?:hey\s+|ok(?:ay)?[,!]?\s*|please\s+|pls\s+|kindly\s+|also\s+|just\s+|now\s+)?
        (?:
            (?:(?:can|could|would)\s+you\s+|let'?s\s+|go\s+ahead\s+and\s+)?
            \b(?:build|create|design|develop|make|generate|code|write|lay\s+out|lay|put\s+together|
                draft|sketch|render|give|show|rebuild|redesign|prototype)\b
          |
            \b(?:i|we|you)\s+(?:want|need|wish|would\s+like|asking\s+for)\b
        )
        \s+(?:you\s+to\s+)?(?:me\s+|us\s+|him\s+|her\s+)?(?:to\s+)?
        (?:(?:a|an|the|my|our|one|single|full|complete|whole|simple|new|modern|clean|responsive|
             professional|quick|nice|beautiful|proper|basic|small|static|free|landing|web|site|
             page|portfolio|business|personal|company|cafe|coffee|restaurant|online)\s+)*
        \b(?:website|web\s*site|webpage|web\s*page|site|page|landing\s+page|home\s*page|
            homepage|portfolio|blog|store|shop)\b
        \s*(?:for\s+me\s*)?
        (?:\s+(?:with|without|including|using|featuring|that\s+(?:has|have|includes|uses))\s+
             [^,.!?]*?(?=\s+(?:for|of|about|named|called)\s))?
        (?:[,.:;]\s*|\s+|$)
    """
)
_SUBJECT_LEAD = re.compile(
    r"""(?ix)^\s*(?:for|of|about|on|covering|named|called|to\s+promote|to\s+sell|and)\s+"""
)


def _subject_line(value: Any) -> str:
    """What the page is about, with the request that asked for it cut off.

    Returns the line unchanged when no request phrase leads it, so a brief that
    already names only the subject is never shortened by guessing.
    """
    first = next((line.strip() for line in str(value or "").splitlines() if line.strip()), "")
    if not first:
        return ""
    lead = _SITE_REQUEST.search(first)
    if not lead:
        return _text(first)
    subject = _SUBJECT_LEAD.sub("", first[lead.end():], count=1)
    # A sentence that is nothing but the request ("design a website") names no
    # subject, and the caller refuses rather than inventing one.
    return _text(re.split(r"[!?]|\.(?=\s+[A-Z])", subject)[0]).strip(" -,.:;!?")


def _palette_for(subject: str) -> tuple[str, str, str]:
    digest = hashlib.sha256(subject.casefold().encode("utf-8")).digest()
    return PALETTES[digest[0] % len(PALETTES)]


def _readable_on(hex_color: str) -> str:
    """White or ink on a solid brand colour — a supplied accent may be a pale yellow."""
    digits = hex_color.lstrip("#")
    if len(digits) == 3:
        digits = "".join(char * 2 for char in digits)
    red, green, blue = (int(digits[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return "#12151c" if 0.2126 * red + 0.7152 * green + 0.0722 * blue > 0.55 else "#ffffff"


def _split_card(item: str) -> tuple[str, str]:
    """A bullet reads as a card when it carries its own heading."""
    text = _text(item)
    for separator in (" — ", " - ", ": "):
        head, _, tail = text.partition(separator)
        if separator in text and 2 <= len(head) <= 60 and tail.strip():
            return _trimmed(head, 60), _trimmed(tail, CARD_BODY_LIMIT)
    return _trimmed(text, 60), ""


def _body_for(headline: str, snippet: str) -> str:
    """A news snippet often repeats its own headline — sometimes truncated to less
    of it than the headline carries. Pairing the two prints the same sentence twice
    with a dash in the middle, in whichever order the source sent it.

    Measured live: "Best Treks in Nepal for 2026: … Explore a… — Best Treks in
    Nepal for 2026: … Explore a…" on one card.
    """
    body = snippet.casefold()
    if not body:
        return ""
    if body.startswith(headline.casefold()):
        return snippet[len(headline):].strip(" —:-,.")
    if headline.casefold().startswith(body.rstrip("…")):
        return ""
    return snippet


async def _research_material(subject: str) -> tuple[list[tuple[str, str]], list[Block], list[tuple[str, str]]]:
    """Cards, blocks and links built out of live findings — each line keeps its address."""
    from .deep_research import deep_research_handler

    try:
        outcome = await deep_research_handler({"topic": subject, "depth": 24})
    except Exception as error:  # noqa: BLE001 - a dead pass must refuse, not fall back to boilerplate
        logger.warning("Research pass for the site failed for '%s': %s", subject, error)
        return [], [], []

    data = outcome.get("data") if isinstance(outcome, dict) and outcome.get("status") == "success" else None
    items = (data or {}).get("items") or []

    cards: list[tuple[str, str]] = []
    links: list[tuple[str, str]] = []
    grouped: dict[str, list[dict[str, str]]] = {}
    seen: set[str] = set()
    for item in items:
        headline = _text(item.get("title") or item.get("url"))
        if not headline or headline.casefold() in seen:
            continue
        seen.add(headline.casefold())
        body = _body_for(headline, _text(item.get("snippet") or ""))
        snippet = _trimmed(body, CARD_BODY_LIMIT)
        url = _text(item.get("url"))
        if len(cards) < MAX_CARDS:
            # A finding promoted to a card is shown in full there; re-listing it
            # under its source would print the same page twice over.
            cards.append((_trimmed(headline, 60), snippet))
        else:
            grouped.setdefault(_text(item.get("source") or "web"), []).append(
                {"headline": headline, "url": url, "snippet": snippet}
            )
        if url and len(links) < MAX_TEXT_LINKS * 3:
            links.append((headline, url))

    blocks: list[Block] = []
    for source, group in grouped.items():
        block = Block(heading=f"{source.title()} findings", anchor="")
        for finding in group[:MAX_TEXT_LINKS]:
            text = f"{finding['headline']} — {finding['snippet']}" if finding["snippet"] else finding["headline"]
            block.bullets.append(_trimmed(text, 700))
        if block.bullets:
            blocks.append(block)
    return cards, blocks, links


def _content_material(content: str) -> tuple[list[tuple[str, str]], list[Block], list[tuple[str, str]]]:
    """His own copy, laid out as written. The exporter formats, never authors."""
    sections = _build_user_content_sections(_scrub_chat_affection(content))
    blocks: list[Block] = []
    cards: list[tuple[str, str]] = []
    links: list[tuple[str, str]] = []
    for index, (heading, raw_blocks) in enumerate(sections):
        block = Block(heading=_text(heading) or f"Section {index + 1}", anchor=_anchor_for(_text(heading), index))
        donated: list[str] = []
        for raw in raw_blocks:
            if isinstance(raw, list):
                if raw and isinstance(raw[0], list):
                    block.table = [[_text(cell) for cell in row] for row in raw]
                else:
                    values = [_text(cell) for cell in raw if _text(cell)]
                    block.bullets.extend(values)
                    if not cards and len(values) >= 3:
                        cards = [_split_card(value) for value in values[:MAX_CARDS]]
                        donated = values[:MAX_CARDS]
            elif _text(raw):
                if not block.lead:
                    block.lead = _text(raw)
                else:
                    block.bullets.append(_text(raw))
        for url in _URL.finditer(block.lead + " " + " ".join(block.bullets)):
            links.append((url.group(0)[:80], url.group(0)))
        if donated:
            block.bullets = [item for item in block.bullets if item not in donated]
        if block.lead or block.bullets or block.table:
            blocks.append(block)
    return cards, blocks, links[:MAX_TEXT_LINKS]


class NoSiteSource(Exception):
    def __init__(self, subject: str, reason: str):
        super().__init__(reason)
        self.subject = subject
        self.reason = reason


async def _build_plan(params: DesignWebsiteParams) -> SitePlan:
    supplied = (params.content or "").strip()
    brief = str(params.brief or "").strip()
    if not supplied and len([line for line in brief.splitlines() if line.strip()]) > 1:
        # He sent the copy in the same message as the request, so the page is
        # laid out from his words instead of researched from them.
        supplied = brief
    subject = _subject_line(params.brief) or _text(params.subject) or _text(params.query) or \
        _text(params.prompt) or _text(params.topic) or _text(params.title)

    if supplied:
        cards, blocks, links = _content_material(supplied)
        provenance = "supplied-text"
        if not blocks and not cards:
            raise NoSiteSource(_trimmed(subject, 80) or "this site",
                               "The copy you sent parsed to no readable section.")
    else:
        if not subject:
            raise NoSiteSource(
                subject or "this site",
                "No subject was named and no copy was supplied.",
            )
        cards, blocks, links = await _research_material(_trimmed(subject, 240))
        provenance = "live-research"
        if not blocks and not cards:
            raise NoSiteSource(_trimmed(subject, 80),
                               "No research source answered, so there is no real material to lay out.")

    used_anchors: set[str] = set()
    for index, block in enumerate(blocks):
        anchor = block.anchor or _anchor_for(block.heading, index)
        while anchor in used_anchors:
            anchor = f"{anchor}-{index}"
        used_anchors.add(anchor)
        block.anchor = anchor

    title = _trimmed(_text(params.title), 90) or _trimmed(subject, 60) or "Untitled site"
    accent, accent_2, surface = _palette_for(subject or title)
    if params.accent and _ACCENT.match(params.accent.strip()):
        accent = params.accent.strip()
    elif params.accent:
        logger.info("Ignoring unvalidated accent %r", params.accent)

    return SitePlan(
        title=title,
        eyebrow="Designed from your brief" if provenance == "supplied-text" else "Designed from live findings",
        tagline=_trimmed(subject, 220) if subject and subject.casefold() != title.casefold() else (
            _text(blocks[0].lead) if blocks and blocks[0].lead else ""
        ),
        accent=accent,
        accent_2=accent_2,
        on_accent=_readable_on(accent),
        surface=surface,
        theme=(params.theme or "auto").lower(),
        cards=cards,
        blocks=blocks,
        links=links,
        provenance=provenance,
    )


def render_site(plan: SitePlan) -> str:
    """One file, no JavaScript, nothing interpolated that was not escaped."""
    nav_items = [
        f'<a class="nav-link" href="#{block.anchor}">{_esc(block.heading)}</a>'
        for block in plan.blocks[:5]
    ]
    nav = "\n        ".join(nav_items) or '<a class="nav-link" href="#top">Top</a>'

    first_target = "top-of-work" if plan.cards else (plan.blocks[0].anchor if plan.blocks else "top")
    hero_ctas = [f'<a class="btn btn-primary" href="#{first_target}">See the sections</a>']
    if plan.links:
        hero_ctas.append('<a class="btn btn-ghost" href="#sources">Where this came from</a>')
    hero_actions = "\n        ".join(hero_ctas)

    cards_html = ""
    if plan.cards:
        tiles = "\n".join(
            f"""        <article class="card reveal">
          <h3>{_esc(head)}</h3>
          {f"<p>{_esc(body)}</p>" if body else ""}
        </article>"""
            for head, body in plan.cards
        )
        cards_html = f"""
    <section class="band" id="top-of-work" aria-labelledby="cards-h">
      <div class="wrap">
        <h2 id="cards-h" class="band-title">Highlights</h2>
        <div class="cards">
{tiles}
        </div>
      </div>
    </section>"""

    blocks_html: list[str] = []
    for index, block in enumerate(plan.blocks):
        if not block.heading and not block.lead and not block.bullets and not block.table:
            continue
        parts = [f'    <section class="band{" band-alt" if index % 2 else ""}" id="{_esc(block.anchor)}">',
                 '      <div class="wrap">',
                 f'        <h2 class="band-title">{_esc(block.heading or "Details")}</h2>']
        if block.lead:
            parts.append(f'        <p class="lead reveal">{_esc(block.lead)}</p>')
        if block.bullets:
            parts.append('        <ul class="list">')
            parts.extend(f'          <li class="reveal">{_esc(item)}</li>' for item in block.bullets[:MAX_TEXT_LINKS])
            parts.append("        </ul>")
        if block.table:
            header, *rows = block.table
            parts.append('        <div class="table-wrap"><table><thead><tr>')
            parts.extend(f"          <th>{_esc(cell)}</th>" for cell in header)
            parts.append("        </tr></thead><tbody>")
            for row in rows:
                parts.append("          <tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in row) + "</tr>")
            parts.append("        </tbody></table></div>")
        parts.extend(["      </div>", "    </section>"])
        blocks_html.append("\n".join(parts))

    sources_html = ""
    if plan.links:
        items = "\n".join(
            f'          <li><a href="{_esc(url)}" rel="noopener noreferrer nofollow" target="_blank">{_esc(label)}</a></li>'
            for label, url in plan.links[:MAX_TEXT_LINKS]
            if url.startswith(("http://", "https://"))
        )
        if items:
            sources_html = f"""
    <section class="band" id="sources" aria-labelledby="sources-h">
      <div class="wrap">
        <h2 id="sources-h" class="band-title">Where this came from</h2>
        <p class="lead">Every line on this page was either written by you in this session or fetched live.
        These are the addresses behind them.</p>
        <ul class="sources">
{items}
        </ul>
      </div>
    </section>"""

    tagline_html = f'<p class="tagline rise-late">{_esc(plan.tagline)}</p>' if plan.tagline else ""
    sections_html = "\n".join(blocks_html)

    theme_css = {
        "light": ":root{color-scheme:light}",
        "dark": (
            ":root{color-scheme:dark;--ink:#eef1f7;--paper:#0e1117;--muted:#a7b0c2;"
            "--line:rgba(238,241,247,.13);--card:#161b26}"
        ),
        "auto": (
            "@media (prefers-color-scheme: dark){:root{--ink:#eef1f7;--paper:#0e1117;"
            "--muted:#a7b0c2;--line:rgba(238,241,247,.13);--card:#161b26}}"
        ),
    }.get(plan.theme, "")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(plan.title)}</title>
<meta name="description" content="{_esc(plan.tagline or plan.title)}">
<meta name="generator" content="HINAA website design">
<style>
:root {{
  --accent: {plan.accent};
  --accent-2: {plan.accent_2};
  --on-accent: {plan.on_accent};
  --paper: {plan.surface};
  --ink: #12151c;
  --muted: #5b6474;
  --line: rgba(18, 21, 28, .10);
  --card: #ffffff;
  --step--1: clamp(.83rem, .8rem + .12vw, .89rem);
  --step-0: clamp(1rem, .97rem + .14vw, 1.08rem);
  --step-1: clamp(1.25rem, 1.17rem + .38vw, 1.5rem);
  --step-2: clamp(1.56rem, 1.4rem + .78vw, 2.1rem);
  --step-3: clamp(2rem, 1.6rem + 1.9vw, 3.2rem);
  --gutter: clamp(1.1rem, 4vw, 3.5rem);
  --radius: 18px;
  color-scheme: light dark;
}}
{theme_css}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;background:var(--paper);color:var(--ink);font:400 var(--step-0)/1.62 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Inter,Roboto,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{width:min(100% - (var(--gutter) * 2),74rem);margin-inline:auto}}
a{{color:inherit}}
:focus-visible{{outline:3px solid var(--accent);outline-offset:3px;border-radius:6px}}

.masthead{{position:sticky;top:0;z-index:20;background:var(--paper);background:color-mix(in oklab,var(--paper) 82%,transparent);backdrop-filter:blur(14px) saturate(140%);border-bottom:1px solid var(--line)}}
.masthead .wrap{{display:flex;align-items:center;gap:1rem;justify-content:space-between;min-height:3.9rem;flex-wrap:wrap}}
.brand{{display:flex;align-items:center;gap:.6rem;font-weight:750;letter-spacing:-.02em;text-decoration:none;font-size:var(--step-1)}}
.brand i{{width:.85rem;height:.85rem;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent-2));box-shadow:0 0 0 4px color-mix(in oklab,var(--accent) 18%,transparent)}}
nav{{display:flex;gap:.2rem;flex-wrap:wrap}}
.nav-link{{text-decoration:none;font-size:var(--step--1);font-weight:600;color:var(--muted);padding:.45rem .7rem;border-radius:999px;transition:color .18s,background-color .18s}}
.nav-link:hover{{color:var(--ink);background:rgba(127,127,127,.14);background:color-mix(in oklab,var(--accent) 10%,transparent)}}

.hero{{position:relative;isolation:isolate;overflow:hidden;padding:clamp(3.2rem,9vw,7rem) 0 clamp(2.6rem,6vw,4.6rem)}}
.hero::before,.hero::after{{content:"";position:absolute;z-index:-1;border-radius:50%;filter:blur(60px)}}
.hero::before{{top:-18%;right:-14%;width:46vmax;height:46vmax;opacity:.42;background:radial-gradient(circle at 32% 32%,var(--accent),transparent 66%)}}
.hero::after{{bottom:-30%;left:-18%;width:42vmax;height:42vmax;opacity:.34;background:radial-gradient(circle at 62% 42%,var(--accent-2),transparent 68%)}}
.grid-lines{{position:absolute;inset:0;z-index:-1;opacity:.5;background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:56px 56px;mask-image:radial-gradient(circle at 50% 25%,#000,transparent 72%)}}
.eyebrow{{display:inline-flex;align-items:center;gap:.5rem;margin:0 0 1rem;font-size:var(--step--1);font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}}
.eyebrow span{{width:1.6rem;height:2px;background:currentColor;border-radius:2px}}
h1{{margin:0;font-size:var(--step-3);line-height:1.06;letter-spacing:-.03em;font-weight:800;text-wrap:balance}}
.tagline{{margin:1.1rem 0 0;max-width:56ch;font-size:var(--step-1);line-height:1.5;color:var(--muted);text-wrap:pretty}}
.actions{{display:flex;gap:.7rem;flex-wrap:wrap;margin-top:1.8rem}}
.btn{{display:inline-flex;align-items:center;gap:.5rem;padding:.78rem 1.35rem;border-radius:999px;font-weight:700;font-size:var(--step-0);text-decoration:none;border:1px solid transparent;transition:transform .18s cubic-bezier(.2,.7,.2,1),box-shadow .18s,background-color .18s}}
.btn-primary{{background:var(--accent);color:var(--on-accent);box-shadow:0 12px 26px -14px color-mix(in oklab,var(--accent) 80%,#000)}}
.btn-primary:hover{{transform:translateY(-2px);box-shadow:0 18px 34px -14px color-mix(in oklab,var(--accent) 80%,#000)}}
.btn-ghost{{border-color:var(--line);background:var(--card);background:color-mix(in oklab,var(--card) 70%,transparent)}}
.btn-ghost:hover{{transform:translateY(-2px);border-color:var(--accent);color:var(--accent)}}

.band{{padding:clamp(2.4rem,6vw,4.4rem) 0;border-top:1px solid var(--line)}}
.band-alt{{background:var(--paper);background:color-mix(in oklab,var(--card) 55%,var(--paper))}}
.band-title{{margin:0 0 1.5rem;font-size:var(--step-2);line-height:1.15;letter-spacing:-.022em;font-weight:780}}
.lead{{margin:0 0 1.4rem;max-width:68ch;color:var(--muted);font-size:var(--step-1);line-height:1.55}}
.cards{{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(min(100%,17rem),1fr))}}
.card{{position:relative;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:1.35rem 1.35rem 1.5rem;overflow:hidden;transition:transform .22s cubic-bezier(.2,.7,.2,1),box-shadow .22s,border-color .22s}}
.card::after{{content:"";position:absolute;inset:auto 0 0 0;height:3px;background:linear-gradient(90deg,var(--accent),var(--accent-2));transform:scaleX(0);transform-origin:left;transition:transform .3s cubic-bezier(.2,.7,.2,1)}}
.card:hover,.card:focus-within{{transform:translateY(-4px);box-shadow:0 22px 40px -26px rgba(12,16,24,.5);border-color:color-mix(in oklab,var(--accent) 34%,var(--line))}}
.card:hover::after,.card:focus-within::after{{transform:scaleX(1)}}
.card h3{{margin:0 0 .5rem;font-size:var(--step-1);line-height:1.25;letter-spacing:-.012em}}
.card p{{margin:0;color:var(--muted);font-size:var(--step-0);line-height:1.58}}
.list{{margin:0;padding:0;display:grid;gap:.55rem;list-style:none}}
.list li{{position:relative;padding-left:1.5rem;color:var(--muted);line-height:1.6}}
.list li::before{{content:"";position:absolute;left:.1rem;top:.62em;width:.55rem;height:.55rem;border-radius:2px;background:linear-gradient(135deg,var(--accent),var(--accent-2));transform:rotate(45deg)}}
.table-wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:var(--radius);background:var(--card)}}
table{{border-collapse:collapse;width:100%;font-size:var(--step--1)}}
th,td{{padding:.7rem .85rem;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:color-mix(in oklab,var(--accent) 8%,var(--card));font-weight:750;white-space:nowrap}}
tbody tr:last-child td{{border-bottom:0}}
.sources{{margin:0;padding:0;list-style:none;display:grid;gap:.5rem;font-size:var(--step--1)}}
.sources a{{color:var(--accent);text-decoration:none;border-bottom:1px solid color-mix(in oklab,var(--accent) 30%,transparent);transition:border-color .18s}}
.sources a:hover{{border-color:var(--accent)}}
footer{{border-top:1px solid var(--line);padding:2.2rem 0 3rem;color:var(--muted);font-size:var(--step--1)}}
footer .wrap{{display:flex;gap:.6rem;flex-wrap:wrap;justify-content:space-between;align-items:baseline}}

@media (prefers-reduced-motion: no-preference) {{
  .rise{{animation:rise .68s cubic-bezier(.2,.7,.2,1) both}}
  .rise-late{{animation:rise .68s .1s cubic-bezier(.2,.7,.2,1) both}}
  .hero::before{{animation:drift-a 19s ease-in-out infinite alternate}}
  .hero::after{{animation:drift-b 23s ease-in-out infinite alternate}}
  @keyframes rise{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:none}}}}
  @keyframes drift-a{{to{{transform:translate3d(-4%,6%,0) scale(1.08)}}}}
  @keyframes drift-b{{to{{transform:translate3d(5%,-5%,0) scale(1.06)}}}}
}}
@supports (animation-timeline: view()) {{
  @media (prefers-reduced-motion: no-preference) {{
    .reveal{{animation:reveal linear both;animation-timeline:view();animation-range:entry 4% cover 30%}}
    @keyframes reveal{{from{{opacity:0;transform:translateY(22px) scale(.985)}}to{{opacity:1;transform:none}}}}
  }}
}}
</style>
</head>
<body id="top">
  <header class="masthead">
    <div class="wrap">
      <a class="brand" href="#top"><i aria-hidden="true"></i>{_esc(plan.title)}</a>
      <nav aria-label="Sections">{nav}</nav>
    </div>
  </header>

  <main>
    <section class="hero">
      <div class="grid-lines" aria-hidden="true"></div>
      <div class="wrap">
        <p class="eyebrow rise"><span aria-hidden="true"></span>{_esc(plan.eyebrow)}</p>
        <h1 class="rise">{_esc(plan.title)}</h1>
        {tagline_html}
        <div class="actions rise-late">
        {hero_actions}
        </div>
      </div>
    </section>
{cards_html}
{sections_html}
{sources_html}
  </main>

  <footer>
    <div class="wrap">
      <span>Laid out by HINAA · body source: {_esc(plan.provenance.replace('-', ' '))}</span>
      <span>Single file · no scripts · responsive</span>
    </div>
  </footer>
</body>
</html>
"""


async def website_design_handler(params: DesignWebsiteParams) -> dict[str, Any]:
    """Compose the page, write it beside the other documents, answer a live preview URL."""
    try:
        plan = await _build_plan(params)
    except NoSiteSource as error:
        return {
            "status": "error",
            "code": "WEBSITE_NO_SOURCE",
            "subject": error.subject,
            "error": (
                f"No website was built for '{error.subject}'. {error.reason} Send me the copy to lay out, "
                f"or ask again once the research sources answer — I will not fill a page with invented "
                f"features, prices, or testimonials."
            ),
        }

    unique_links: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for label, url in plan.links:
        if url not in seen_urls:
            seen_urls.add(url)
            unique_links.append((label, url))
    plan.links = unique_links

    site_id = str(uuid.uuid4())
    filename = f"{_sanitize_slug(plan.title)}.html"
    file_path = DOCS_DIR / f"{site_id}_{filename}"
    payload = render_site(plan).encode("utf-8")
    file_path.write_bytes(payload)

    result = {
        "status": "success",
        "format": "html",
        "mimeType": "text/html; charset=utf-8",
        "provider": "local-layout-engine",
        "docId": site_id,
        "title": plan.title,
        "filename": filename,
        "previewUrl": f"/api/v1/generated-docs/{site_id}/preview",
        "downloadUrl": f"/api/v1/generated-docs/{site_id}",
        "sections": [block.heading for block in plan.blocks if block.heading],
        "highlightCount": len(plan.cards),
        "linkCount": len(plan.links),
        "contentSource": plan.provenance,
        "fileSizeBytes": len(payload),
        "fileSizeKb": round(len(payload) / 1024, 1),
        "summary": (
            f"Laid out '{plan.title}' as a responsive single-file page ({round(len(payload) / 1024, 1)} KB) "
            f"with {len(plan.blocks)} section(s) and {len(plan.cards)} highlight card(s) from "
            f"{plan.provenance.replace('-', ' ')} material."
        ),
    }
    file_path.with_suffix(".site.json").write_text(
        json.dumps({**result, "ownerId": params.userId or "unattributed"}, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.info("Designed site %s: %s (%d bytes, %s)", site_id, filename, len(payload), plan.provenance)
    return result


website_design_def = ToolDefinition(
    name="design_website",
    display_name="Design Website",
    description=(
        "Design a complete responsive website and return a live preview URL plus a downloadable file. "
        "`content` is laid out verbatim; without it the page copy comes from a live multi-source research "
        "pass on `brief`. Layout is composed here, words never are — the tool answers WEBSITE_NO_SOURCE "
        "rather than inventing features, prices, or testimonials."
    ),
    parameters={
        "brief": {"type": "string", "description": "What the site is for, in the owner's words"},
        "content": {"type": "string", "description": "Copy to lay out verbatim"},
        "title": {"type": "string", "description": "Name shown in the page header"},
        "accent": {"type": "string", "description": "Brand colour as #hex"},
        "theme": {"type": "string", "enum": ["light", "dark", "auto"], "description": "Colour scheme"},
    },
    required_parameters=[],
    requires_confirmation=False,
    risk_level="medium",
    side_effects="Writes a persistent HTML page into the workspace documents store.",
)

registry.register(website_design_def, website_design_handler)
