"""Markdown → PDF document renderer for HINAA reports.

Purpose-built for the two things users actually export: assistant answers and
deep-research dossiers — both of which are markdown. The renderer keeps a
deliberate visual hierarchy (branded header band, numbered pages, styled
sections, tables, shaded code blocks) so the file reads like a document, not
a terminal dump.

Unicode policy: HINAA's answers can contain Devanagari or curly typography.
When a system font covering those glyphs exists (Nirmala on Windows, DejaVu or
Lohit on Linux) it is embedded; otherwise text is transliterated losslessly
where possible and latin-1-sanitized so generation never crashes mid-report.
"""

from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

_FONT_CANDIDATES: tuple[Path, ...] = (
    Path("C:/Windows/Fonts/Nirmala.ttf"),
    Path("C:/Windows/Fonts/malgun.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
)

_MONO_CANDIDATES: tuple[Path, ...] = (
    Path("C:/Windows/Fonts/consolas.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
)

_PUNCTUATION_MAP = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2026": "...",
    "\u00a0": " ", "\u2022": "-", "\u2192": "->", "\u2190": "<-",
})


def _latin_safe(text: str) -> str:
    text = text.translate(_PUNCTUATION_MAP)
    return text.encode("latin-1", "replace").decode("latin-1").replace("?", "")


def _find_font(candidates: tuple[Path, ...]) -> str | None:
    for path in candidates:
        if path.is_file():
            return str(path)
    return None


_INLINE = [
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"(?<![\w*])\*([^*\n]+)\*(?!\*)"), r"\1"),
    (re.compile(r"~~([^~]+)~~"), r"\1"),
    (re.compile(r"`([^`]+)`"), r"\1"),
    # Keep link text but append the URL once — a printed page must stay useful.
    (re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)"), r"\1 (\2)"),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"[image: \1]"),
]


def _inline(text: str) -> str:
    for pattern, replacement in _INLINE:
        text = pattern.sub(replacement, text)
    return re.sub(r"\s{2,}", " ", text).strip()


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s:|-]*-{2,}[\s:|-]*\|?\s*$", line)) and "-" in line


class _HinaaDoc(FPDF):
    """FPDF with a per-page branded footer (fpdf2 paints footer() automatically)."""

    footer_note = "HINAA"
    footer_family = "helvetica"
    footer_sanitize = staticmethod(lambda t: t)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_font(self.footer_family, "", 8)
        self.set_text_color(150, 144, 160)
        self.cell(0, 5, self.footer_sanitize(f"{self.footer_note} · page {self.page_no()}"), align="C")


def render_markdown_pdf(markdown: str, *, title: str = "HINAA Report", subtitle: str | None = None) -> bytes:
    """Render markdown into a polished A4 PDF; returns the file bytes."""
    pdf = _HinaaDoc(orientation="P", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(16, 16, 16)

    unicode_font = _find_font(_FONT_CANDIDATES)
    mono_font = _find_font(_MONO_CANDIDATES)
    body_family = "helvetica"
    mono_family = "courier"
    if unicode_font:
        try:
            for style in ("", "B", "I", "BI"):
                pdf.add_font("hinaa", style, unicode_font)  # one face, all slots
            body_family = "hinaa"
        except Exception:  # noqa: BLE001 - font issues must degrade, never crash
            unicode_font = None
    if unicode_font is None and mono_font:
        try:
            pdf.add_font("hinamono", "", mono_font)
            mono_family = "hinamono"
        except Exception:  # noqa: BLE001
            pass
    sanitize = (lambda t: t) if unicode_font else _latin_safe

    def emit(width: float, text: str, *, style: str = "", size: int = 10, lead: float = 1.34,
             fill: bool = False, indent: float = 0.0, color: tuple[int, int, int] | None = None) -> None:
        if not text:
            return
        pdf.set_font(body_family, style, size)
        pdf.set_text_color(*(color or (28, 26, 33)))
        x = pdf.get_x() + indent
        pdf.set_x(x)
        pdf.multi_cell(width - indent, size * lead * 0.4233, sanitize(text), new_x="LMARGIN", new_y="NEXT", fill=fill)

    # ── cover band ──
    pdf.add_page()
    pdf.set_fill_color(238, 145, 173)
    pdf.rect(0, 0, 210, 30, "F")
    pdf.set_xy(16, 8)
    pdf.set_font(body_family, "B", 15)
    pdf.set_text_color(48, 20, 40)
    pdf.cell(0, 8, sanitize("◇ HINAA"))
    pdf.set_xy(16, 36)
    pdf.set_font(body_family, "B", 20)
    pdf.set_text_color(28, 26, 33)
    pdf.multi_cell(178, 9, sanitize(title), new_x="LMARGIN", new_y="NEXT")
    stamp = datetime.now().strftime("%d %b %Y, %H:%M")
    pdf.set_font(body_family, "", 9)
    pdf.set_text_color(120, 112, 128)
    pdf.cell(0, 6, sanitize((subtitle + " · " if subtitle else "") + stamp))
    pdf.ln(10)
    pdf.set_draw_color(226, 199, 240)
    pdf.line(16, pdf.get_y(), 194, pdf.get_y())
    pdf.ln(6)

    lines = re.sub(r"\r\n?", "\n", markdown).split("\n")
    i = 0
    while i < len(lines):
        before = i
        line = lines[i]
        stripped = line.strip()

        # fenced code
        fence = re.match(r"^\s*```(\w*)\s*$", line)
        if fence:
            block: list[str] = []
            i += 1
            while i < len(lines) and not re.match(r"^\s*```\s*$", lines[i]):
                block.append(lines[i])
                i += 1
            i += 1
            pdf.set_font(mono_family, "", 8.4)
            pdf.set_fill_color(246, 244, 250)
            pdf.set_text_color(70, 60, 90)
            body = sanitize("\n".join(block)) if block else ""
            if body:
                pdf.multi_cell(178, 4.4, body, new_x="LMARGIN", new_y="NEXT", fill=True)
            pdf.ln(3)
            continue

        # headings
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = _inline(heading.group(2))
            if level <= 2:
                pdf.ln(2)
                emit(178, text, style="B", size=15 if level == 1 else 13, color=(150, 60, 110))
                pdf.set_draw_color(238, 145, 173)
                if level == 1:
                    pdf.line(16, pdf.get_y(), 90, pdf.get_y())
                    pdf.ln(1)
                pdf.ln(2)
            else:
                pdf.ln(1)
                emit(178, text, style="B", size=11.5, color=(88, 60, 130))
                pdf.ln(1)
            i += 1
            continue

        # hr
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            pdf.set_draw_color(214, 208, 224)
            pdf.line(16, pdf.get_y() + 1, 194, pdf.get_y() + 1)
            pdf.ln(4)
            i += 1
            continue

        # table
        if "|" in line and i + 1 < len(lines) and _is_separator(lines[i + 1]):
            header = _split_table_row(line)
            rows: list[list[str]] = []
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_split_table_row(lines[i]))
                i += 1
            try:
                pdf.set_font(body_family, "", 8.8)
                with pdf.table(
                    line_height=5.4, text_align="LEFT", padding=1.6,
                    headings_style=FontFace(family=body_family, emphasis="BOLD", size_pt=9),
                    cell_fill_color=(246, 244, 250), cell_fill_mode="ROWS",
                    line_color=(214, 208, 224), width=178,
                ) as table:
                    header_row = table.row()
                    for cell_text in header:
                        header_row.cell(sanitize(_inline(cell_text)))
                    for row in rows[:60]:
                        body_row = table.row()
                        for cell_text in row:
                            body_row.cell(sanitize(_inline(cell_text)))
            except Exception:  # noqa: BLE001 - a malformed table must not kill the document
                for row in [header] + rows:
                    emit(178, "  ".join(_inline(c) for c in row), size=9)
            pdf.ln(3)
            continue

        # blockquote
        if stripped.startswith(">"):
            quote: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            pdf.set_font(body_family, "I", 9.6)
            pdf.set_text_color(96, 84, 110)
            pdf.set_x(22)
            pdf.multi_cell(166, 5.0, sanitize(_inline(" ".join(quote))), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            continue

        # lists
        item = re.match(r"^(\s*)(?:[-*•]|\d+[.)])\s+(.*)$", line)
        if item:
            depth = min(len(item.group(1)) // 2, 3)
            ordered = bool(re.match(r"^\s*\d+[.)]", line))
            text = _inline(item.group(2))
            bullet = "•" if not ordered else ""
            if ordered:
                emit(178, text, indent=4 + depth * 6, size=9.8)
            else:
                pdf.set_font(body_family, "", 9.8)
                pdf.set_x(16 + depth * 6)
                pdf.set_text_color(150, 60, 110)
                pdf.cell(5, 5, sanitize(bullet))
                pdf.set_text_color(28, 26, 33)
                pdf.multi_cell(173 - depth * 6, 4.15, sanitize(text), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.6)
            i += 1
            continue

        # blank line
        if not stripped:
            i += 1
            continue

        # paragraph (greedy until blank/structural line)
        para: list[str] = []
        while i < len(lines):
            current = lines[i]
            if not current.strip() or re.match(r"^\s*(#{1,6}\s|```|>|[-*•]\s|\d+[.)]\s|-{3,}\s*$)", current):
                break
            if "|" in current and i + 1 < len(lines) and _is_separator(lines[i + 1]):
                break
            para.append(current.strip())
            i += 1
        if para:
            emit(178, _inline(" ".join(para)), size=10)
            pdf.ln(2.2)
        if i == before:  # defensive: no branch may stall the cursor
            i += 1

    pdf.footer_family = body_family
    pdf.footer_sanitize = sanitize
    return bytes(pdf.output())


def safe_filename(title: str, fallback: str = "hinaa-report") -> str:
    slug = re.sub(r"[^a-z0-9\u0900-\u097F]+", "-", title.lower()).strip("-")
    return f"{slug[:60] or fallback}.pdf"
