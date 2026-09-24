"""Phase 14 — Artifact OS: Native PPTX (PresentationML) Exporter.

Produces valid Microsoft PowerPoint (.pptx) presentation decks in pure Python.
"""
from __future__ import annotations

import io
import xml.sax.saxutils as sax
import zipfile
from typing import Any

from ..document_ast import (
    DocumentAST,
    HeadingNode,
    ListNode,
    ParagraphNode,
    SlideNode,
)
from ..models import ArtifactFormat
from .base import BaseExporter


def _escape(text: str) -> str:
    return sax.escape(text)


PPTX_CONTENT_TYPES_HEADER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
"""

PPTX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""

SLIDE_MASTER_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst>
    <p:sldLayoutId id="2147483649" r:id="rId1"/>
  </p:sldLayoutIdLst>
</p:sldMaster>"""

SLIDE_LAYOUT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="titleAndContent">
  <p:cSld name="Title and Content">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
    </p:spTree>
  </p:cSld>
</p:sldLayout>"""

SLIDE_LAYOUT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""

SLIDE_MASTER_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""


class PptxExporter(BaseExporter):
    """Generates standard Microsoft PowerPoint (.pptx) presentation decks."""

    format = ArtifactFormat.PPTX

    def export(self, doc: DocumentAST, **kwargs: Any) -> bytes:
        slides = list(doc.slides)

        # Synthesize slides from document sections if doc.slides is empty
        if not slides:
            # First slide: title
            slides.append(SlideNode(
                title=doc.title,
                subtitle=doc.subtitle or f"Prepared by {doc.author}",
                layout="title",
            ))

            current_slide: SlideNode | None = None
            for node in doc.children:
                if isinstance(node, HeadingNode) and node.level in (1, 2):
                    if current_slide:
                        slides.append(current_slide)
                    current_slide = SlideNode(title=node.text, bullets=[])
                elif isinstance(node, ParagraphNode) and current_slide:
                    current_slide.bullets.append(node.plain_text)
                elif isinstance(node, ListNode) and current_slide:
                    for item in node.items:
                        current_slide.bullets.append(item.plain_text)

            if current_slide:
                slides.append(current_slide)

        if not slides:
            slides.append(SlideNode(title=doc.title or "Presentation", layout="title"))

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # 1. Content Types
            ct_lines = [PPTX_CONTENT_TYPES_HEADER]
            for i in range(1, len(slides) + 1):
                ct_lines.append(
                    f'  <Override PartName="/ppt/slides/slide{i}.xml" '
                    'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
                )
            ct_lines.append("</Types>")
            zf.writestr("[Content_Types].xml", "\n".join(ct_lines))

            # 2. Package relationships
            zf.writestr("_rels/.rels", PPTX_RELS)

            # 3. Master & layout
            zf.writestr("ppt/slideMasters/slideMaster1.xml", SLIDE_MASTER_XML)
            zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", SLIDE_MASTER_RELS)
            zf.writestr("ppt/slideLayouts/slideLayout1.xml", SLIDE_LAYOUT_XML)
            zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", SLIDE_LAYOUT_RELS)

            # 4. Presentation XML
            pres_sld_ids: list[str] = []
            pres_rels: list[str] = [
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
            ]

            for i, _slide in enumerate(slides, start=1):
                rid = f"rId{i + 1}"
                sld_id = 255 + i
                pres_sld_ids.append(f'<p:sldId id="{sld_id}" r:id="{rid}"/>')
                pres_rels.append(
                    f'  <Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
                )
            pres_rels.append("</Relationships>")

            presentation_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
                '  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>\n'
                f'  <p:sldIdLst>{"".join(pres_sld_ids)}</p:sldIdLst>\n'
                '  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>\n'
                '</p:presentation>'
            )
            zf.writestr("ppt/presentation.xml", presentation_xml)
            zf.writestr("ppt/_rels/presentation.xml.rels", "\n".join(pres_rels))

            # 5. Individual slides
            for i, slide in enumerate(slides, start=1):
                slide_xml = self._build_slide_xml(slide)
                zf.writestr(f"ppt/slides/slide{i}.xml", slide_xml)
                zf.writestr(
                    f"ppt/slides/_rels/slide{i}.xml.rels",
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                    '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>\n'
                    '</Relationships>'
                )

        return buf.getvalue()

    def _build_slide_xml(self, slide: SlideNode) -> str:
        title_esc = _escape(slide.title)
        subtitle_esc = _escape(slide.subtitle)

        # Title shape
        title_shape = (
            '<p:sp>'
            '<p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="838200" y="609600"/><a:ext cx="10515600" cy="1143000"/></a:xfrm></p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/>'
            f'<a:p><a:r><a:rPr lang="en-US" sz="4000" b="1"><a:solidFill><a:srgbClr val="1E293B"/></a:solidFill></a:rPr><a:t>{title_esc}</a:t></a:r></a:p>'
            '</p:txBody>'
            '</p:sp>'
        )

        body_paragraphs: list[str] = []
        if subtitle_esc:
            body_paragraphs.append(
                f'<a:p><a:r><a:rPr lang="en-US" sz="2400" i="1"><a:solidFill><a:srgbClr val="64748B"/></a:solidFill></a:rPr><a:t>{subtitle_esc}</a:t></a:r></a:p>'
            )

        for bullet in slide.bullets[:8]:  # Clamp to reasonable slide limit
            b_esc = _escape(bullet)
            body_paragraphs.append(
                f'<a:p><a:pPr lvl="0"/><a:r><a:rPr lang="en-US" sz="2000"><a:solidFill><a:srgbClr val="334155"/></a:solidFill></a:rPr><a:t>{b_esc}</a:t></a:r></a:p>'
            )

        content_shape = ""
        if body_paragraphs:
            content_shape = (
                '<p:sp>'
                '<p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>'
                '<p:spPr><a:xfrm><a:off x="838200" y="2057400"/><a:ext cx="10515600" cy="4114800"/></a:xfrm></p:spPr>'
                f'<p:txBody><a:bodyPr/><a:lstStyle/>{"".join(body_paragraphs)}</p:txBody>'
                '</p:sp>'
            )

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            '  <p:cSld><p:spTree>\n'
            '    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>\n'
            '    <p:grpSpPr/>\n'
            f'    {title_shape}\n'
            f'    {content_shape}\n'
            '  </p:spTree></p:cSld>\n'
            '</p:sld>'
        )
