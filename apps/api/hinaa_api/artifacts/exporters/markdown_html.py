"""Phase 14 — Artifact OS: Markdown and HTML Exporters."""
from __future__ import annotations

import html
from typing import Any

from ..document_ast import (
    ASTNode,
    CalloutNode,
    CodeBlockNode,
    DividerNode,
    DocumentAST,
    HeadingNode,
    ImageNode,
    InlineSpan,
    ListNode,
    PageBreakNode,
    ParagraphNode,
    TableNode,
)
from ..models import ArtifactFormat
from .base import BaseExporter


def _spans_to_md(spans: list[InlineSpan]) -> str:
    parts: list[str] = []
    for s in spans:
        t = s.text
        if s.code:
            t = f"`{t}`"
        if s.bold and s.italic:
            t = f"***{t}***"
        elif s.bold:
            t = f"**{t}**"
        elif s.italic:
            t = f"*{t}*"
        if s.strikethrough:
            t = f"~~{t}~~"
        if s.link_url:
            t = f"[{t}]({s.link_url})"
        parts.append(t)
    return "".join(parts)


def _spans_to_html(spans: list[InlineSpan]) -> str:
    parts: list[str] = []
    for s in spans:
        t = html.escape(s.text)
        if s.code:
            t = f"<code>{t}</code>"
        if s.bold:
            t = f"<strong>{t}</strong>"
        if s.italic:
            t = f"<em>{t}</em>"
        if s.strikethrough:
            t = f"<del>{t}</del>"
        if s.link_url:
            safe_url = html.escape(s.link_url, quote=True)
            t = f'<a href="{safe_url}" target="_blank" rel="noopener">{t}</a>'
        parts.append(t)
    return "".join(parts)


class MarkdownExporter(BaseExporter):
    """Serializes DocumentAST into standard GitHub-Flavored Markdown."""

    format = ArtifactFormat.MD

    def export(self, doc: DocumentAST, **kwargs: Any) -> str:
        lines: list[str] = []

        for node in doc.children:
            if isinstance(node, HeadingNode):
                prefix = "#" * node.level
                lines.append(f"\n{prefix} {_spans_to_md(node.spans)}\n")

            elif isinstance(node, ParagraphNode):
                lines.append(f"\n{_spans_to_md(node.spans)}\n")

            elif isinstance(node, ListNode):
                lines.append("")
                for idx, item in enumerate(node.items, start=node.start):
                    bullet = f"{idx}." if node.ordered else "-"
                    check = ""
                    if item.checked is True:
                        check = "[x] "
                    elif item.checked is False:
                        check = "[ ] "
                    lines.append(f"{bullet} {check}{_spans_to_md(item.spans)}")
                lines.append("")

            elif isinstance(node, TableNode):
                lines.append("")
                if node.headers:
                    h_cells = [_spans_to_md(c.spans) for c in node.headers.cells]
                    lines.append("| " + " | ".join(h_cells) + " |")
                    lines.append("| " + " | ".join(["---"] * len(h_cells)) + " |")
                for row in node.rows:
                    r_cells = [_spans_to_md(c.spans) for c in row.cells]
                    lines.append("| " + " | ".join(r_cells) + " |")
                lines.append("")

            elif isinstance(node, CodeBlockNode):
                lang = node.language or ""
                lines.append(f"\n```{lang}\n{node.code}\n```\n")

            elif isinstance(node, CalloutNode):
                lines.append(f"\n> [!{node.kind.value}] {node.title}")
                for b in node.blocks:
                    if isinstance(b, ParagraphNode):
                        for subline in _spans_to_md(b.spans).split("\n"):
                            lines.append(f"> {subline}")
                lines.append("")

            elif isinstance(node, ImageNode):
                lines.append(f"\n![{node.alt_text or node.caption}]({node.url})\n")

            elif isinstance(node, DividerNode):
                lines.append("\n---\n")

            elif isinstance(node, PageBreakNode):
                lines.append("\n<!-- pagebreak -->\n")

        return "\n".join(lines).strip() + "\n"


class HtmlExporter(BaseExporter):
    """Renders DocumentAST into responsive, modern, standalone HTML5."""

    format = ArtifactFormat.HTML

    def export(self, doc: DocumentAST, **kwargs: Any) -> str:
        body_parts: list[str] = []

        for node in doc.children:
            if isinstance(node, HeadingNode):
                tag = f"h{min(node.level, 6)}"
                aid = f' id="{html.escape(node.anchor_id)}"' if node.anchor_id else ""
                body_parts.append(f"<{tag}{aid}>{_spans_to_html(node.spans)}</{tag}>")

            elif isinstance(node, ParagraphNode):
                align_style = f' style="text-align: {node.align};"' if node.align != "left" else ""
                body_parts.append(f"<p{align_style}>{_spans_to_html(node.spans)}</p>")

            elif isinstance(node, ListNode):
                tag = "ol" if node.ordered else "ul"
                items: list[str] = []
                for item in node.items:
                    check_html = ""
                    if item.checked is True:
                        check_html = '<input type="checkbox" checked disabled> '
                    elif item.checked is False:
                        check_html = '<input type="checkbox" disabled> '
                    items.append(f"<li>{check_html}{_spans_to_html(item.spans)}</li>")
                body_parts.append(f"<{tag}>\n  " + "\n  ".join(items) + f"\n</{tag}>")

            elif isinstance(node, TableNode):
                rows_html: list[str] = []
                if node.headers:
                    th_cells = "".join(f"<th>{_spans_to_html(c.spans)}</th>" for c in node.headers.cells)
                    rows_html.append(f"  <thead><tr>{th_cells}</tr></thead>")
                tbody_rows: list[str] = []
                for row in node.rows:
                    td_cells = "".join(f"<td>{_spans_to_html(c.spans)}</td>" for c in row.cells)
                    tbody_rows.append(f"  <tr>{td_cells}</tr>")
                rows_html.append("  <tbody>\n  " + "\n  ".join(tbody_rows) + "\n  </tbody>")
                caption_html = f"<caption>{html.escape(node.caption)}</caption>\n" if node.caption else ""
                body_parts.append(f"<table>\n{caption_html}" + "\n".join(rows_html) + "\n</table>")

            elif isinstance(node, CodeBlockNode):
                lang_cls = f' class="language-{html.escape(node.language)}"' if node.language else ""
                escaped_code = html.escape(node.code)
                body_parts.append(f"<pre><code{lang_cls}>{escaped_code}</code></pre>")

            elif isinstance(node, CalloutNode):
                kind_lower = node.kind.value.lower()
                content_html: list[str] = []
                for b in node.blocks:
                    if isinstance(b, ParagraphNode):
                        content_html.append(f"<p>{_spans_to_html(b.spans)}</p>")
                inner = "".join(content_html)
                title_html = f'<div class="callout-title"><strong>{html.escape(node.title)}</strong></div>'
                body_parts.append(f'<div class="callout callout-{kind_lower}">\n{title_html}\n{inner}\n</div>')

            elif isinstance(node, ImageNode):
                safe_url = html.escape(node.url, quote=True)
                safe_alt = html.escape(node.alt_text or node.caption, quote=True)
                caption = f"<figcaption>{html.escape(node.caption)}</figcaption>" if node.caption else ""
                body_parts.append(f'<figure><img src="{safe_url}" alt="{safe_alt}">{caption}</figure>')

            elif isinstance(node, DividerNode):
                body_parts.append("<hr>")

            elif isinstance(node, PageBreakNode):
                body_parts.append('<div class="page-break"></div>')

        content_html_str = "\n".join(body_parts)
        safe_title = html.escape(doc.title)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <style>
    :root {{
      --font-sans: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
      --bg: #ffffff;
      --fg: #1e293b;
      --border: #e2e8f0;
      --accent: #ec4899;
      --code-bg: #f8fafc;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #0f172a;
        --fg: #f8fafc;
        --border: #334155;
        --code-bg: #1e293b;
      }}
    }}
    body {{
      font-family: var(--font-sans);
      color: var(--fg);
      background-color: var(--bg);
      line-height: 1.6;
      max-width: 860px;
      margin: 0 auto;
      padding: 2rem 1.5rem;
    }}
    h1, h2, h3, h4, h5, h6 {{ line-height: 1.25; margin-top: 1.5em; margin-bottom: 0.5em; font-weight: 600; }}
    h1 {{ font-size: 2.25rem; border-bottom: 2px solid var(--border); padding-bottom: 0.3em; }}
    h2 {{ font-size: 1.75rem; border-bottom: 1px solid var(--border); padding-bottom: 0.2em; }}
    h3 {{ font-size: 1.35rem; }}
    code {{ font-family: var(--font-mono); background: var(--code-bg); padding: 0.2em 0.4em; border-radius: 4px; font-size: 0.9em; }}
    pre {{ background: var(--code-bg); border: 1px solid var(--border); padding: 1rem; border-radius: 8px; overflow-x: auto; }}
    pre code {{ background: none; padding: 0; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1.5rem 0; }}
    th, td {{ border: 1px solid var(--border); padding: 0.75rem; text-align: left; }}
    th {{ background: var(--code-bg); font-weight: 600; }}
    hr {{ border: 0; border-top: 1px solid var(--border); margin: 2rem 0; }}
    .callout {{ border-left: 4px solid #3b82f6; background: rgba(59, 130, 246, 0.08); padding: 1rem; border-radius: 0 8px 8px 0; margin: 1.5rem 0; }}
    .callout-tip {{ border-color: #10b981; background: rgba(16, 185, 129, 0.08); }}
    .callout-important {{ border-color: #8b5cf6; background: rgba(139, 92, 246, 0.08); }}
    .callout-warning {{ border-color: #f59e0b; background: rgba(245, 158, 11, 0.08); }}
    .callout-caution {{ border-color: #ef4444; background: rgba(239, 68, 68, 0.08); }}
    .page-break {{ page-break-after: always; }}
    @media print {{
      body {{ max-width: 100%; padding: 0; }}
      .page-break {{ page-break-after: always; }}
    }}
  </style>
</head>
<body>
<header>
  <h1>{safe_title}</h1>
</header>
<main>
{content_html_str}
</main>
</body>
</html>
"""
