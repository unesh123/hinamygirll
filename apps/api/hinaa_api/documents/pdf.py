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
    "\u25c6": "*", "\u25c7": "*", "\u25aa": "-", "\u25a0": "-",
    "\u25b8": ">", "\u25cf": "*", "\u2713": "[v]", "\u2714": "[v]",
    "\u2716": "[x]", "\u2717": "[x]", "\u00b7": "·",
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
    """FPDF with executive per-page running header and branded footer."""

    footer_note = "HINAA EXECUTIVE INTELLIGENCE STUDIO"
    footer_family = "helvetica"
    footer_sanitize = staticmethod(_latin_safe)

    def header(self) -> None:
        # Running top header on page 2+
        if self.page_no() > 1:
            self.set_y(8)
            self.set_font(self.footer_family, "B", 7.5)
            self.set_text_color(100, 116, 139)
            self.cell(100, 4, self.footer_sanitize("HINAA EXECUTIVE DOSSIER"), align="L")
            self.set_font(self.footer_family, "", 7.5)
            self.cell(78, 4, self.footer_sanitize("CONFIDENTIAL // RESTRICTED"), align="R")
            self.set_draw_color(226, 232, 240)
            self.set_line_width(0.3)
            self.line(16, 13.5, 194, 13.5)

    def footer(self) -> None:
        self.set_y(-14)
        self.set_draw_color(226, 232, 240)
        self.set_line_width(0.3)
        self.line(16, self.get_y(), 194, self.get_y())
        self.ln(2)
        self.set_font(self.footer_family, "", 7.5)
        self.set_text_color(148, 163, 184)
        self.cell(110, 5, self.footer_sanitize(f"{self.footer_note} | AUTONOMOUS AGENT SYSTEM"), align="L")
        self.set_font(self.footer_family, "B", 7.5)
        self.set_text_color(100, 116, 139)
        self.cell(68, 5, self.footer_sanitize(f"PAGE {self.page_no()} OF {{nb}}"), align="R")


def render_markdown_pdf(markdown: str, *, title: str = "HINAA Report", subtitle: str | None = None) -> bytes:
    """Render markdown into an executive publication-grade A4 PDF; returns the file bytes."""
    pdf = _HinaaDoc(orientation="P", format="A4")
    pdf.alias_nb_pages()
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
    pdf.footer_family = body_family
    pdf.footer_sanitize = sanitize

    def emit(width: float, text: str, *, style: str = "", size: int = 10, lead: float = 1.34,
             fill: bool = False, indent: float = 0.0, color: tuple[int, int, int] | None = None) -> None:
        if not text:
            return
        pdf.set_font(body_family, style, size)
        pdf.set_text_color(*(color or (28, 26, 33)))
        x = pdf.get_x() + indent
        pdf.set_x(x)
        pdf.multi_cell(width - indent, size * lead * 0.4233, sanitize(text), new_x="LMARGIN", new_y="NEXT", fill=fill)

    # ── executive header band ──
    pdf.add_page()
    # Dark obsidian top bar
    pdf.set_fill_color(15, 23, 42)
    pdf.rect(0, 0, 210, 24, "F")
    # Vibrant Sky Cyan accent strip beneath
    pdf.set_fill_color(56, 189, 248)
    pdf.rect(0, 24, 210, 1.5, "F")

    # Brand Title in header
    pdf.set_xy(16, 7)
    pdf.set_font(body_family, "B", 13)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(32, 6, sanitize("◆ HINAA"))
    pdf.set_font(body_family, "", 7.8)
    pdf.set_text_color(148, 163, 184)
    pdf.set_xy(48, 7.8)
    pdf.cell(70, 5, sanitize("EXECUTIVE INTELLIGENCE DOSSIER"))

    # Status classification pill in top-right
    pdf.set_fill_color(30, 41, 59)
    pdf.set_draw_color(56, 189, 248)
    pdf.set_line_width(0.3)
    pdf.rect(132, 6, 62, 7.5, style="DF", round_corners=True, corner_radius=2)
    pdf.set_xy(132, 7.2)
    pdf.set_font(body_family, "B", 6.8)
    pdf.set_text_color(56, 189, 248)
    pdf.cell(62, 5, sanitize("CONFIDENTIAL // STRATEGIC BRIEF"), align="C")

    # Document Title Block
    pdf.set_xy(16, 31)
    pdf.set_font(body_family, "B", 19)
    pdf.set_text_color(15, 23, 42)
    pdf.multi_cell(178, 8.5, sanitize(title), new_x="LMARGIN", new_y="NEXT")

    stamp = datetime.now().strftime("%d %b %Y, %H:%M")
    if subtitle:
        pdf.set_font(body_family, "I", 9.5)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(178, 5.0, sanitize(subtitle), new_x="LMARGIN", new_y="NEXT")

    # Executive Metadata Card (Rounded 4-column grid)
    y_meta = pdf.get_y() + 2
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    pdf.set_line_width(0.3)
    pdf.rect(16, y_meta, 178, 12, style="DF", round_corners=True, corner_radius=2)

    col_w = 178.0 / 4.0
    meta_items = [
        ("DOCUMENT REF", "HNA-AUTO-2026"),
        ("DATE & TIME", stamp),
        ("SECURITY LEVEL", "RESTRICTED"),
        ("SYSTEM CORE", "FRONTIER COGNITIVE"),
    ]
    for idx, (label, val) in enumerate(meta_items):
        cx = 16 + idx * col_w
        pdf.set_xy(cx + 3, y_meta + 1.8)
        pdf.set_font(body_family, "B", 6.2)
        pdf.set_text_color(148, 163, 184)
        pdf.cell(col_w - 6, 3.5, sanitize(label))

        pdf.set_xy(cx + 3, y_meta + 5.8)
        pdf.set_font(body_family, "B", 7.5)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(col_w - 6, 4.2, sanitize(val))

    pdf.set_y(y_meta + 15)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(16, pdf.get_y(), 194, pdf.get_y())
    pdf.ln(5)

    lines = re.sub(r"\r\n?", "\n", markdown).split("\n")
    i = 0
    while i < len(lines):
        before = i
        line = lines[i]
        stripped = line.strip()

        # fenced code & architecture blueprints
        fence = re.match(r"^\s*```(\w*)\s*$", line)
        if fence:
            lang = (fence.group(1) or "").lower()
            block: list[str] = []
            i += 1
            while i < len(lines) and not re.match(r"^\s*```\s*$", lines[i]):
                block.append(lines[i])
                i += 1
            i += 1
            body = sanitize("\n".join(block)) if block else ""
            if not body:
                continue

            is_arch = lang == "mermaid" or any(
                body.strip().startswith(kw)
                for kw in ("graph", "flowchart", "sequenceDiagram", "classDiagram", "erDiagram", "stateDiagram")
            )

            pill_title = "📐 ARCHITECTURE BLUEPRINT & TOPOLOGY" if is_arch else f"CODE [{lang.upper() or 'SNIPPET'}]"
            box_bg = (15, 23, 42) if is_arch else (24, 24, 27)
            text_color = (226, 232, 240) if is_arch else (241, 245, 249)
            accent_pill = (56, 189, 248) if is_arch else (148, 163, 184)

            pdf.set_font(mono_family, "", 8.0)
            wrapped_lines: list[str] = []
            for b_line in block[:60]:
                b_sub = pdf.multi_cell(168, 4.0, sanitize(b_line) or " ", dry_run=True, output="LINES")
                wrapped_lines.extend(b_sub)

            total_h = len(wrapped_lines) * 4.0 + 10.0
            if total_h < 150 and pdf.will_page_break(total_h + 3):
                pdf.add_page()

            y_top = pdf.get_y()
            if not pdf.will_page_break(total_h + 3):
                pdf.set_fill_color(*box_bg)
                pdf.set_draw_color(51, 65, 85)
                pdf.set_line_width(0.3)
                pdf.rect(16, y_top, 178, total_h, style="DF", round_corners=True, corner_radius=2)

                pdf.set_xy(20, y_top + 2.0)
                pdf.set_font(body_family, "B", 7.2)
                pdf.set_text_color(*accent_pill)
                pdf.cell(168, 3.5, sanitize(pill_title))

                pdf.set_xy(20, y_top + 6.5)
                pdf.set_font(mono_family, "", 8.0)
                pdf.set_text_color(*text_color)
                for wl in wrapped_lines:
                    pdf.set_x(20)
                    pdf.cell(168, 4.0, sanitize(wl), new_x="LMARGIN", new_y="NEXT")

                pdf.set_y(y_top + total_h + 3)
            else:
                pdf.set_fill_color(*box_bg)
                pdf.set_font(body_family, "B", 7.2)
                pdf.set_text_color(*accent_pill)
                pdf.multi_cell(178, 5.0, sanitize(f" {pill_title}"), fill=True, new_x="LMARGIN", new_y="NEXT")

                pdf.set_font(mono_family, "", 8.0)
                pdf.set_text_color(*text_color)
                pdf.multi_cell(178, 4.0, body, fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)

            continue

        # headings
        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = _inline(heading.group(2))
            try:
                pdf.start_section(sanitize(text), level=min(level - 1, 2))
            except Exception:
                pass
            if level == 1:
                if pdf.will_page_break(18):
                    pdf.add_page()
                pdf.ln(3)
                emit(178, text, style="B", size=15, color=(15, 23, 42))
                pdf.set_draw_color(56, 189, 248)
                pdf.set_line_width(0.8)
                pdf.line(16, pdf.get_y(), 66, pdf.get_y())
                pdf.ln(2.5)
            elif level == 2:
                if pdf.will_page_break(14):
                    pdf.add_page()
                pdf.ln(2.5)
                pdf.set_font(body_family, "B", 12.5)
                pdf.set_text_color(56, 189, 248)
                pdf.cell(4, 5.5, sanitize("•"))
                emit(174, text, style="B", size=12.5, color=(30, 41, 59))
                pdf.ln(1.5)
            else:
                if pdf.will_page_break(10):
                    pdf.add_page()
                pdf.ln(1.5)
                emit(178, text, style="B", size=10.5, color=(71, 85, 105))
                pdf.ln(1)
            i += 1
            continue

        # hr
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            pdf.set_draw_color(226, 232, 240)
            pdf.set_line_width(0.3)
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
                pdf.set_draw_color(226, 232, 240)
                pdf.set_font(body_family, "", 8.8)
                with pdf.table(
                    line_height=5.6, text_align="LEFT", padding=2.2,
                    headings_style=FontFace(family=body_family, emphasis="BOLD", size_pt=8.8, color=(255, 255, 255), fill_color=(15, 23, 42)),
                    cell_fill_color=(248, 250, 252), cell_fill_mode="ROWS",
                    width=178,
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

        # blockquote & GitHub alerts (> [!NOTE], > [!TIP], > [!IMPORTANT], > [!WARNING], > [!CAUTION])
        if stripped.startswith(">"):
            raw_quote_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                raw_quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            if not raw_quote_lines:
                continue

            first_line = raw_quote_lines[0]
            alert_match = re.match(
                r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](?:\s+(.*))?$",
                first_line,
                re.I,
            )

            if alert_match:
                alert_kind = alert_match.group(1).upper()
                custom_hdr = alert_match.group(2) or ""
                body_parts: list[str] = []
                if custom_hdr:
                    body_parts.append(custom_hdr)
                body_parts.extend(raw_quote_lines[1:])
                alert_text = _inline(" ".join(body_parts)).strip()

                ALERT_CONFIGS: dict[str, dict[str, Any]] = {
                    "NOTE": {
                        "accent": (2, 132, 199),
                        "bg": (240, 249, 255),
                        "border": (186, 230, 253),
                        "badge": "NOTE // ARCHITECTURAL CONTEXT",
                    },
                    "TIP": {
                        "accent": (22, 163, 74),
                        "bg": (240, 253, 244),
                        "border": (187, 247, 208),
                        "badge": "PRO-TIP // EFFICIENCY BEST PRACTICE",
                    },
                    "IMPORTANT": {
                        "accent": (124, 58, 237),
                        "bg": (250, 245, 255),
                        "border": (233, 213, 255),
                        "badge": "CRITICAL SPECIFICATION // MANDATORY REQUIREMENT",
                    },
                    "WARNING": {
                        "accent": (217, 119, 6),
                        "bg": (255, 251, 235),
                        "border": (254, 243, 199),
                        "badge": "OPERATIONAL WARNING // SYSTEM RISK",
                    },
                    "CAUTION": {
                        "accent": (225, 29, 72),
                        "bg": (255, 241, 242),
                        "border": (254, 205, 211),
                        "badge": "CAUTION // HIGH-RISK INVARIANT",
                    },
                }
                cfg = ALERT_CONFIGS.get(alert_kind, ALERT_CONFIGS["NOTE"])

                pdf.set_font(body_family, "", 9.2)
                wrapped_lines = pdf.multi_cell(166, 4.4, sanitize(alert_text) if alert_text else " ", dry_run=True, output="LINES")
                total_box_h = max(14.0, len(wrapped_lines) * 4.4 + 9.5)

                if pdf.will_page_break(total_box_h + 3):
                    pdf.add_page()

                y_top = pdf.get_y()
                pdf.set_fill_color(*cfg["bg"])
                pdf.set_draw_color(*cfg["border"])
                pdf.set_line_width(0.3)
                pdf.rect(16, y_top, 178, total_box_h, style="DF", round_corners=True, corner_radius=2)

                pdf.set_fill_color(*cfg["accent"])
                pdf.rect(16, y_top, 3.2, total_box_h, style="F")

                pdf.set_xy(22, y_top + 2.5)
                pdf.set_font(body_family, "B", 8)
                pdf.set_text_color(*cfg["accent"])
                pdf.cell(168, 4.5, sanitize(cfg["badge"]))

                if alert_text:
                    pdf.set_xy(22, y_top + 7.2)
                    pdf.set_font(body_family, "", 9.2)
                    pdf.set_text_color(30, 41, 59)
                    pdf.multi_cell(168, 4.4, sanitize(alert_text), new_x="LMARGIN", new_y="NEXT")

                pdf.set_y(y_top + total_box_h + 3)
                continue
            else:
                quote_text = _inline(" ".join(raw_quote_lines))
                pdf.set_font(body_family, "I", 9.5)
                wrapped_lines = pdf.multi_cell(166, 4.8, sanitize(quote_text), dry_run=True, output="LINES")
                total_box_h = max(12.0, len(wrapped_lines) * 4.8 + 6.0)

                if pdf.will_page_break(total_box_h + 3):
                    pdf.add_page()

                y_top = pdf.get_y()
                pdf.set_fill_color(248, 250, 252)
                pdf.set_draw_color(226, 232, 240)
                pdf.set_line_width(0.3)
                pdf.rect(16, y_top, 178, total_box_h, style="DF", round_corners=True, corner_radius=2)

                pdf.set_fill_color(148, 163, 184)
                pdf.rect(16, y_top, 2.5, total_box_h, style="F")

                pdf.set_xy(22, y_top + 3.0)
                pdf.set_font(body_family, "I", 9.5)
                pdf.set_text_color(71, 85, 105)
                pdf.multi_cell(168, 4.8, sanitize(quote_text), new_x="LMARGIN", new_y="NEXT")
                pdf.set_y(y_top + total_box_h + 3)
                continue

        # lists
        item = re.match(r"^(\s*)(?:[-*•]|\d+[.)])\s+(.*)$", line)
        if item:
            depth = min(len(item.group(1)) // 2, 3)
            ordered = bool(re.match(r"^\s*\d+[.)]", line))
            text = _inline(item.group(2))
            if ordered:
                num_match = re.match(r"^\s*(\d+[.)])\s+(.*)$", line)
                num_str = num_match.group(1) if num_match else "1."
                pdf.set_font(body_family, "B", 9.5)
                pdf.set_x(16 + depth * 6)
                pdf.set_text_color(15, 23, 42)
                pdf.cell(7, 4.6, sanitize(num_str))
                pdf.set_font(body_family, "", 9.5)
                pdf.set_text_color(30, 41, 59)
                pdf.multi_cell(171 - depth * 6, 4.6, sanitize(text), new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.set_font(body_family, "B", 9.5)
                pdf.set_x(16 + depth * 6)
                pdf.set_text_color(56, 189, 248)
                pdf.cell(5, 4.6, sanitize("•"))
                pdf.set_font(body_family, "", 9.5)
                pdf.set_text_color(30, 41, 59)
                pdf.multi_cell(173 - depth * 6, 4.6, sanitize(text), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(0.8)
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
        if i == before:
            i += 1

    pdf.footer_family = body_family
    pdf.footer_sanitize = sanitize
    return bytes(pdf.output())


def safe_filename(title: str, fallback: str = "hinaa-report") -> str:
    slug = re.sub(r"[^a-z0-9\u0900-\u097F]+", "-", title.lower()).strip("-")
    return f"{slug[:60] or fallback}.pdf"
