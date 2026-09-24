"""Phase 14 — Artifact OS: Native DOCX (WordprocessingML) Exporter.

Produces valid, standards-compliant Office Open XML (.docx) files in pure Python
without external dependencies.
"""
from __future__ import annotations

import io
import xml.sax.saxutils as sax
import zipfile
from typing import Any

from ..document_ast import (
    CalloutNode,
    CodeBlockNode,
    DividerNode,
    DocumentAST,
    HeadingNode,
    InlineSpan,
    ListNode,
    PageBreakNode,
    ParagraphNode,
    TableNode,
)
from ..models import ArtifactFormat
from .base import BaseExporter

CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOCUMENT_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
        <w:sz w:val="22"/>
        <w:color w:val="2A2A2A"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:after="160" w:line="276" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="400" w:after="180"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="36"/>
      <w:color w:val="1E293B"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="300" w:after="140"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="28"/>
      <w:color w:val="334155"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:before="240" w:after="100"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val="24"/>
      <w:color w:val="475569"/>
    </w:rPr>
  </w:style>
</w:styles>"""


def _escape(text: str) -> str:
    return sax.escape(text)


def _render_spans_to_w_runs(spans: list[InlineSpan]) -> str:
    runs: list[str] = []
    for span in spans:
        rpr_items: list[str] = []
        if span.bold:
            rpr_items.append("<w:b/>")
        if span.italic:
            rpr_items.append("<w:i/>")
        if span.strikethrough:
            rpr_items.append("<w:strike/>")
        if span.code:
            rpr_items.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:highlight w:val="lightGray"/>')

        rpr_xml = f"<w:rPr>{''.join(rpr_items)}</w:rPr>" if rpr_items else ""
        text_xml = f'<w:t xml:space="preserve">{_escape(span.text)}</w:t>'
        runs.append(f"<w:r>{rpr_xml}{text_xml}</w:r>")
    return "".join(runs)


class DocxExporter(BaseExporter):
    """Generates standard Microsoft Word (.docx) documents."""

    format = ArtifactFormat.DOCX

    def export(self, doc: DocumentAST, **kwargs: Any) -> bytes:
        body_xml_parts: list[str] = []

        # Document title
        if doc.title:
            body_xml_parts.append(
                f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
                f'<w:r><w:rPr><w:b/><w:sz w:val="44"/><w:color w:val="0F172A"/></w:rPr>'
                f'<w:t>{_escape(doc.title)}</w:t></w:r></w:p>'
            )

        for node in doc.children:
            if isinstance(node, HeadingNode):
                style_id = f"Heading{min(max(node.level, 1), 3)}"
                runs_xml = _render_spans_to_w_runs(node.spans)
                body_xml_parts.append(
                    f'<w:p><w:pPr><w:pStyle w:val="{style_id}"/></w:pPr>{runs_xml}</w:p>'
                )

            elif isinstance(node, ParagraphNode):
                runs_xml = _render_spans_to_w_runs(node.spans)
                body_xml_parts.append(f"<w:p>{runs_xml}</w:p>")

            elif isinstance(node, ListNode):
                for idx, item in enumerate(node.items, start=node.start):
                    prefix = f"{idx}. " if node.ordered else "• "
                    check_str = ""
                    if item.checked is True:
                        check_str = "[x] "
                    elif item.checked is False:
                        check_str = "[ ] "
                    spans_with_bullet = [InlineSpan(text=f"{prefix}{check_str}")] + item.spans
                    runs_xml = _render_spans_to_w_runs(spans_with_bullet)
                    body_xml_parts.append(
                        f'<w:p><w:pPr><w:ind w:left="480"/></w:pPr>{runs_xml}</w:p>'
                    )

            elif isinstance(node, TableNode):
                tbl_parts: list[str] = [
                    '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
                    '<w:tblBorders>'
                    '<w:top w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
                    '<w:left w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
                    '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
                    '<w:right w:val="single" w:sz="4" w:space="0" w:color="CCCCCC"/>'
                    '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="E5E5E5"/>'
                    '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="E5E5E5"/>'
                    '</w:tblBorders></w:tblPr>'
                ]

                # Headers
                if node.headers:
                    tbl_parts.append("<w:tr><w:trPr><w:tblHeader/></w:trPr>")
                    for cell in node.headers.cells:
                        runs = _render_spans_to_w_runs(cell.spans)
                        tbl_parts.append(
                            f'<w:tc><w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/></w:tcPr>'
                            f'<w:p><w:r><w:rPr><w:b/></w:rPr></w:r>{runs}</w:p></w:tc>'
                        )
                    tbl_parts.append("</w:tr>")

                # Data rows
                for row in node.rows:
                    tbl_parts.append("<w:tr>")
                    for cell in row.cells:
                        runs = _render_spans_to_w_runs(cell.spans)
                        tbl_parts.append(f"<w:tc><w:p>{runs}</w:p></w:tc>")
                    tbl_parts.append("</w:tr>")

                tbl_parts.append("</w:tbl>")
                body_xml_parts.append("".join(tbl_parts))

            elif isinstance(node, CodeBlockNode):
                code_escaped = _escape(node.code)
                lines = code_escaped.split("\n")
                for line in lines:
                    body_xml_parts.append(
                        f'<w:p><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="F8FAFC"/>'
                        f'<w:ind w:left="240" w:right="240"/></w:pPr>'
                        f'<w:r><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr>'
                        f'<w:t xml:space="preserve">{line}</w:t></w:r></w:p>'
                    )

            elif isinstance(node, CalloutNode):
                fill_color = "EFF6FF" if node.kind.value == "NOTE" else "FEF3C7"
                body_xml_parts.append(
                    f'<w:p><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="{fill_color}"/>'
                    f'<w:ind w:left="360" w:right="360"/></w:pPr>'
                    f'<w:r><w:rPr><w:b/><w:color w:val="1E40AF"/></w:rPr>'
                    f'<w:t>[{node.kind.value}] {_escape(node.title)}: </w:t></w:r>'
                )
                for b in node.blocks:
                    if isinstance(b, ParagraphNode):
                        runs = _render_spans_to_w_runs(b.spans)
                        body_xml_parts.append(
                            f'<w:p><w:pPr><w:shd w:val="clear" w:color="auto" w:fill="{fill_color}"/>'
                            f'<w:ind w:left="360" w:right="360"/></w:pPr>{runs}</w:p>'
                        )

            elif isinstance(node, DividerNode):
                body_xml_parts.append(
                    '<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="CBD5E1"/></w:pBdr></w:pPr></w:p>'
                )

            elif isinstance(node, PageBreakNode):
                body_xml_parts.append(
                    '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
                )

        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
            f'  <w:body>{"".join(body_xml_parts)}<w:sectPr/></w:body>\n'
            '</w:document>'
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
            zf.writestr("_rels/.rels", RELS_XML)
            zf.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS_XML)
            zf.writestr("word/styles.xml", STYLES_XML)
            zf.writestr("word/document.xml", document_xml)

        return buf.getvalue()
