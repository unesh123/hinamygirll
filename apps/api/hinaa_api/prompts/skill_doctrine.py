"""Skill doctrine — distilled operating procedures injected into her brain.

Each doctrine is the working core of an external skill pack, compressed to the
rules that change behavior and nothing else (brevity is itself one of the
packs). Doctrines are selected per turn by keyword intent: a greeting carries
none, so casual chat never pays the token cost, and at most two packs plus the
voice rule ride on any single turn.

Pack provenance:
  SUPERPOSE      — plan -> smallest change -> test -> review workflow
  PONYTAIL       — simplicity bias; no unrequested abstraction
  UI_UX          — UI UX Pro Max + Impeccable: hierarchy, restraint, audit
  CODEBASE_MAP   — Graphify + Understand Anything: trace real files, never invent
  ENGINEERING    — Addy Osmani-style shipping discipline: verify before "done"
  DIAGRAM        — Archify: explain systems as components and flows
  CONCISE        — Caveman: spoken answers stay short
"""

from __future__ import annotations

import re

_SUPERPOSE = (
    "ENGINEERING WORKFLOW: For any coding task — 1) State the plan in one line "
    "before writing code. 2) Make the smallest change that satisfies the request. "
    "3) Run or write the test that proves it. 4) Review your own diff for "
    "regressions before presenting it. Never claim done without evidence."
)

_PONYTAIL = (
    "SIMPLICITY BIAS: Choose the simplest solution that works. No new files, "
    "abstractions, config, or dependencies the user did not ask for. If two "
    "approaches tie, pick the one with less code."
)

_UI_UX = (
    "INTERFACE CRAFT: When designing or building UI — one clear visual hierarchy "
    "(one hero element per screen), a restrained palette (one accent, neutrals "
    "for the rest), a consistent spacing scale, readable type sizes, and real "
    "empty/loading/error states. Before delivering, audit your own layout for "
    "alignment, contrast, and orphaned text, and fix what you find."
)

_CODEBASE_MAP = (
    "CODEBASE TRUTH: When answering about or changing this codebase, trace the "
    "real files first — follow actual imports and call sites, then answer with "
    "concrete file paths and symbols. Never invent a file, function, or "
    "architecture that you did not verify exists."
)

_ENGINEERING = (
    "SHIPPING DISCIPLINE: Work is done when it is verified, not when it is "
    "written. State what you changed, how you verified it, and what remains "
    "uncertain. Prefer boring, proven tools over novel ones."
)

_DIAGRAM = (
    "SYSTEM EXPLANATIONS: When explaining architecture or a multi-step system, "
    "structure it as components and the flows between them (A -> B -> C), and "
    "offer to render it as an interactive diagram when that would help."
)

_CONCISE = (
    "VOICE BREVITY: This reply will be spoken aloud. Short sentences. No filler, "
    "no preamble, no lists longer than three items. Say the useful thing first."
)

_CODING_RE = re.compile(
    r"\b(code|coding|bug|debug|debugger|fix|refactor|refactor|test|tests|error|"
    r"exception|function|deploy|commit|repo|repository|pull request|pr review|"
    r"implement|endpoint|api\b|script|compile|build error)\b",
    re.I,
)
_DESIGN_RE = re.compile(
    r"\b(website|web site|landing page|web ?page|ui|ux|design|layout|redesign|"
    r"dashboard|interface|mockup|prototype|logo|poster|theme|styling|css)\b",
    re.I,
)
_CODEBASE_RE = re.compile(
    r"\b(this (codebase|repo|repository|project)|how does .+ work|"
    r"architecture|codebase|file structure|where is .+ (defined|implemented))\b",
    re.I,
)
_SYSTEM_EXPLAIN_RE = re.compile(
    r"\b(diagram|flow|architecture|pipeline|system design|infrastructure|"
    r"how .+ (fits|connects|flows))\b",
    re.I,
)

# Hard ceiling so doctrine can never crowd out history or context.
MAX_DOCTRINE_CHARS = 1600


def doctrine_for_turn(user_text: str, *, is_voice: bool = False) -> str:
    """Select the operating doctrine for this turn.

    Returns "" when the turn needs no doctrine (casual chat stays cheap).
    At most two topical packs plus the voice rule are ever combined.
    """
    text = (user_text or "").strip()
    if not text:
        return ""

    packs: list[str] = []
    if _DESIGN_RE.search(text):
        packs.append(_UI_UX)
    if _CODING_RE.search(text):
        packs.append(_SUPERPOSE)
        packs.append(_PONYTAIL)
        packs.append(_ENGINEERING)
    if _CODEBASE_RE.search(text):
        packs.append(_CODEBASE_MAP)
    if _SYSTEM_EXPLAIN_RE.search(text):
        packs.append(_DIAGRAM)

    # Keep at most two topical doctrines: the first match is the dominant one.
    packs = packs[:2]
    if is_voice:
        packs.append(_CONCISE)
    if not packs:
        return ""

    block = "OPERATING DOCTRINE FOR THIS TURN:\n" + "\n\n".join(packs)
    return block[:MAX_DOCTRINE_CHARS]
