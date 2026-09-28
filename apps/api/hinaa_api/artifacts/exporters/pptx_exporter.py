"""Phase 14 — Artifact OS: Native PPTX (PresentationML) Exporter.

Produces publication-grade, executive Microsoft PowerPoint (.pptx) presentation decks
with responsive multi-card grids, split-column layouts, obsidian dark themes, and
widescreen 16:9 canvas dimensions in pure Python.
"""
from __future__ import annotations

import io
import re
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
    return sax.escape(str(text))


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


def _split_bullet_title(bullet: str) -> tuple[str, str]:
    """Extract optional bold or colon-delimited lead title from a bullet string."""
    m_bold = re.match(r"^\*\*([^*]+)\*\*:?\s*(.*)$", bullet.strip())
    if m_bold:
        return m_bold.group(1).strip(), m_bold.group(2).strip()
    m_colon = re.match(r"^([^:]{3,40}):\s+(.+)$", bullet.strip())
    if m_colon:
        return m_colon.group(1).strip(), m_colon.group(2).strip()
    m_dash = re.match(r"^([^-—]{3,35})\s+[-—]\s+(.+)$", bullet.strip())
    if m_dash:
        return m_dash.group(1).strip(), m_dash.group(2).strip()
    return "", bullet.strip()


class PptxExporter(BaseExporter):
    """Generates standard Microsoft PowerPoint (.pptx) presentation decks with executive obsidian themes."""

    format = ArtifactFormat.PPTX

    def export(self, doc: DocumentAST, **kwargs: Any) -> bytes:
        slides = list(doc.slides)

        # Synthesize slides from document sections if doc.slides is empty
        if not slides:
            # First slide: title
            slides.append(SlideNode(
                title=doc.title,
                subtitle=doc.subtitle or f"Prepared by {doc.author or 'HINAA AI Studio'}",
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

            # 4. Presentation XML (16:9 widescreen: 12192000 x 6858000 EMUs)
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
            total_slides = len(slides)
            for i, slide in enumerate(slides, start=1):
                slide_xml = self._build_slide_xml(slide, slide_idx=i, total_slides=total_slides)
                zf.writestr(f"ppt/slides/slide{i}.xml", slide_xml)
                zf.writestr(
                    f"ppt/slides/_rels/slide{i}.xml.rels",
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                    '  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>\n'
                    '</Relationships>'
                )

        return buf.getvalue()

    def _build_slide_xml(self, slide: SlideNode, slide_idx: int = 1, total_slides: int = 1) -> str:
        # Determine layout
        is_title = slide.layout == "title" or (slide_idx == 1 and not slide.bullets)
        num_bullets = len(slide.bullets)

        if is_title:
            return self._build_title_slide(slide, slide_idx, total_slides)
        elif num_bullets == 2 or slide.layout == "two_column":
            return self._build_two_column_slide(slide, slide_idx, total_slides)
        elif num_bullets == 3:
            return self._build_three_card_slide(slide, slide_idx, total_slides)
        elif num_bullets == 4:
            return self._build_four_card_slide(slide, slide_idx, total_slides)
        else:
            return self._build_content_slide(slide, slide_idx, total_slides)

    # -----------------------------------------------------------------------
    # Slide Layout 1: Executive Title Slide
    # -----------------------------------------------------------------------
    def _build_title_slide(self, slide: SlideNode, slide_idx: int, total_slides: int) -> str:
        title_esc = _escape(slide.title or "Executive Briefing")
        subtitle_esc = _escape(slide.subtitle or "HINAA Autonomous Presentation")

        # Category pill shape
        pill_shape = (
            '<p:sp>'
            '<p:nvSpPr><p:cNvPr id="2" name="Pill"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr>'
            '<a:xfrm><a:off x="838200" y="1100000"/><a:ext cx="3600000" cy="400000"/></a:xfrm>'
            '<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 20000"/></a:avLst></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="1E293B"/></a:solidFill>'
            '<a:ln w="12700"><a:solidFill><a:srgbClr val="38BDF8"/></a:solidFill></a:ln>'
            '</p:spPr>'
            '<p:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/>'
            '<a:p><a:pPr algn="ctr"/><a:r><a:rPr lang="en-US" sz="1100" b="1"><a:solidFill><a:srgbClr val="38BDF8"/></a:solidFill></a:rPr>'
            '<a:t>◆ HINAA EXECUTIVE KEYNOTE ◆</a:t></a:r></a:p>'
            '</p:txBody>'
            '</p:sp>'
        )

        # Title shape
        title_shape = (
            '<p:sp>'
            '<p:nvSpPr><p:cNvPr id="3" name="Title"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="838200" y="1700000"/><a:ext cx="10515600" cy="2000000"/></a:xfrm></p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/>'
            f'<a:p><a:r><a:rPr lang="en-US" sz="4400" b="1"><a:solidFill><a:srgbClr val="F8FAFC"/></a:solidFill></a:rPr><a:t>{title_esc}</a:t></a:r></a:p>'
            '</p:txBody>'
            '</p:sp>'
        )

        # Gradient accent divider line
        divider_shape = (
            '<p:sp>'
            '<p:nvSpPr><p:cNvPr id="4" name="Divider"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr>'
            '<a:xfrm><a:off x="838200" y="3850000"/><a:ext cx="10515600" cy="36000"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="38BDF8"/></a:solidFill>'
            '</p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>'
            '</p:sp>'
        )

        # Subtitle shape
        subtitle_shape = (
            '<p:sp>'
            '<p:nvSpPr><p:cNvPr id="5" name="Subtitle"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="838200" y="4100000"/><a:ext cx="10515600" cy="1200000"/></a:xfrm></p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/>'
            f'<a:p><a:r><a:rPr lang="en-US" sz="2000" i="1"><a:solidFill><a:srgbClr val="94A3B8"/></a:solidFill></a:rPr><a:t>{subtitle_esc}</a:t></a:r></a:p>'
            '</p:txBody>'
            '</p:sp>'
        )

        footer_shapes = self._build_footer_shapes(6, slide_idx, total_slides)

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            '  <p:cSld>\n'
            '    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="0B0F19"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>\n'
            '    <p:spTree>\n'
            '      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>\n'
            '      <p:grpSpPr/>\n'
            f'      {pill_shape}\n'
            f'      {title_shape}\n'
            f'      {divider_shape}\n'
            f'      {subtitle_shape}\n'
            f'      {footer_shapes}\n'
            '    </p:spTree>\n'
            '  </p:cSld>\n'
            '</p:sld>'
        )

    # -----------------------------------------------------------------------
    # Slide Layout 2: 2-Column Split Cards
    # -----------------------------------------------------------------------
    def _build_two_column_slide(self, slide: SlideNode, slide_idx: int, total_slides: int) -> str:
        header_shapes = self._build_slide_header(2, slide.title)
        footer_shapes = self._build_footer_shapes(5, slide_idx, total_slides)

        card_width = 5050000
        card_height = 4300000
        card_y = 1750000
        x_offsets = [838200, 6303800]
        accent_colors = ["38BDF8", "F472B6"]

        cards: list[str] = []
        for idx, bullet in enumerate(slide.bullets[:2]):
            shape_id = 10 + idx
            b_title, b_desc = _split_bullet_title(bullet)
            card_title = b_title or f"Pillar 0{idx + 1}"
            card_desc = b_desc or bullet
            cards.append(self._render_card_shape(
                shape_id=shape_id,
                x=x_offsets[idx],
                y=card_y,
                cx=card_width,
                cy=card_height,
                badge=f"PERSPECTIVE 0{idx + 1}",
                title=card_title,
                desc=card_desc,
                accent_color=accent_colors[idx % len(accent_colors)],
            ))

        return self._wrap_slide_tree(f"{header_shapes}\n{''.join(cards)}\n{footer_shapes}")

    # -----------------------------------------------------------------------
    # Slide Layout 3: 3-Card Grid
    # -----------------------------------------------------------------------
    def _build_three_card_slide(self, slide: SlideNode, slide_idx: int, total_slides: int) -> str:
        header_shapes = self._build_slide_header(2, slide.title)
        footer_shapes = self._build_footer_shapes(5, slide_idx, total_slides)

        card_width = 3300000
        card_height = 4300000
        card_y = 1750000
        x_offsets = [838200, 4446000, 8053800]
        accent_colors = ["38BDF8", "A78BFA", "34D399"]

        cards: list[str] = []
        for idx, bullet in enumerate(slide.bullets[:3]):
            shape_id = 10 + idx
            b_title, b_desc = _split_bullet_title(bullet)
            card_title = b_title or f"Phase 0{idx + 1}"
            card_desc = b_desc or bullet
            cards.append(self._render_card_shape(
                shape_id=shape_id,
                x=x_offsets[idx],
                y=card_y,
                cx=card_width,
                cy=card_height,
                badge=f"STEP 0{idx + 1}",
                title=card_title,
                desc=card_desc,
                accent_color=accent_colors[idx % len(accent_colors)],
            ))

        return self._wrap_slide_tree(f"{header_shapes}\n{''.join(cards)}\n{footer_shapes}")

    # -----------------------------------------------------------------------
    # Slide Layout 4: 4-Card 2x2 Grid
    # -----------------------------------------------------------------------
    def _build_four_card_slide(self, slide: SlideNode, slide_idx: int, total_slides: int) -> str:
        header_shapes = self._build_slide_header(2, slide.title)
        footer_shapes = self._build_footer_shapes(5, slide_idx, total_slides)

        card_width = 5050000
        card_height = 2050000
        x_offsets = [838200, 6303800]
        y_offsets = [1750000, 4000000]
        accent_colors = ["38BDF8", "F472B6", "34D399", "FBBF24"]

        cards: list[str] = []
        for idx, bullet in enumerate(slide.bullets[:4]):
            col = idx % 2
            row = idx // 2
            shape_id = 10 + idx
            b_title, b_desc = _split_bullet_title(bullet)
            card_title = b_title or f"Component 0{idx + 1}"
            card_desc = b_desc or bullet
            cards.append(self._render_card_shape(
                shape_id=shape_id,
                x=x_offsets[col],
                y=y_offsets[row],
                cx=card_width,
                cy=card_height,
                badge=f"MODULE 0{idx + 1}",
                title=card_title,
                desc=card_desc,
                accent_color=accent_colors[idx % len(accent_colors)],
            ))

        return self._wrap_slide_tree(f"{header_shapes}\n{''.join(cards)}\n{footer_shapes}")

    # -----------------------------------------------------------------------
    # Slide Layout 5: Standard Multi-Bullet Container Slide
    # -----------------------------------------------------------------------
    def _build_content_slide(self, slide: SlideNode, slide_idx: int, total_slides: int) -> str:
        header_shapes = self._build_slide_header(2, slide.title)
        footer_shapes = self._build_footer_shapes(5, slide_idx, total_slides)

        container_x = 838200
        container_y = 1750000
        container_cx = 10515600
        container_cy = 4300000

        paragraphs: list[str] = []
        if slide.subtitle:
            paragraphs.append(
                f'<a:p><a:r><a:rPr lang="en-US" sz="1600" i="1"><a:solidFill><a:srgbClr val="94A3B8"/></a:solidFill></a:rPr><a:t>{_escape(slide.subtitle)}</a:t></a:r></a:p>'
            )

        for b_idx, bullet in enumerate(slide.bullets[:7]):
            b_title, b_desc = _split_bullet_title(bullet)
            if b_title:
                paragraphs.append(
                    f'<a:p><a:pPr spaceBefore="120000" spaceAfter="40000"/>'
                    f'<a:r><a:rPr lang="en-US" sz="1700" b="1"><a:solidFill><a:srgbClr val="38BDF8"/></a:solidFill></a:rPr><a:t>▸ {_escape(b_title)}: </a:t></a:r>'
                    f'<a:r><a:rPr lang="en-US" sz="1600"><a:solidFill><a:srgbClr val="E2E8F0"/></a:solidFill></a:rPr><a:t>{_escape(b_desc)}</a:t></a:r>'
                    f'</a:p>'
                )
            else:
                paragraphs.append(
                    f'<a:p><a:pPr spaceBefore="80000"/>'
                    f'<a:r><a:rPr lang="en-US" sz="1600"><a:solidFill><a:srgbClr val="38BDF8"/></a:solidFill></a:rPr><a:t>• </a:t></a:r>'
                    f'<a:r><a:rPr lang="en-US" sz="1600"><a:solidFill><a:srgbClr val="E2E8F0"/></a:solidFill></a:rPr><a:t>{_escape(bullet)}</a:t></a:r>'
                    f'</a:p>'
                )

        container_shape = (
            '<p:sp>'
            '<p:nvSpPr><p:cNvPr id="10" name="Content Container"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr>'
            f'<a:xfrm><a:off x="{container_x}" y="{container_y}"/><a:ext cx="{container_cx}" cy="{container_cy}"/></a:xfrm>'
            '<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 4000"/></a:avLst></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="161B26"/></a:solidFill>'
            '<a:ln w="12700"><a:solidFill><a:srgbClr val="334155"/></a:solidFill></a:ln>'
            '</p:spPr>'
            f'<p:txBody><a:bodyPr tIns="280000" bIns="280000" lIns="350000" rIns="350000" anchor="t"/><a:lstStyle/>{"".join(paragraphs)}</p:txBody>'
            '</p:sp>'
        )

        return self._wrap_slide_tree(f"{header_shapes}\n{container_shape}\n{footer_shapes}")

    # -----------------------------------------------------------------------
    # Helper Components: Header, Card Shape, Footer
    # -----------------------------------------------------------------------
    def _build_slide_header(self, base_id: int, title: str) -> str:
        title_esc = _escape(title or "Executive Insights")

        accent_bar = (
            '<p:sp>'
            f'<p:nvSpPr><p:cNvPr id="{base_id}" name="Header Accent"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr>'
            '<a:xfrm><a:off x="838200" y="609600"/><a:ext cx="70000" cy="800000"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="38BDF8"/></a:solidFill>'
            '</p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>'
            '</p:sp>'
        )

        title_shape = (
            '<p:sp>'
            f'<p:nvSpPr><p:cNvPr id="{base_id + 1}" name="Title"/><p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="1050000" y="550000"/><a:ext cx="10300000" cy="900000"/></a:xfrm></p:spPr>'
            '<p:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/>'
            f'<a:p><a:r><a:rPr lang="en-US" sz="3000" b="1"><a:solidFill><a:srgbClr val="F8FAFC"/></a:solidFill></a:rPr><a:t>{title_esc}</a:t></a:r></a:p>'
            '</p:txBody>'
            '</p:sp>'
        )

        return f"{accent_bar}\n{title_shape}"

    def _render_card_shape(
        self,
        shape_id: int,
        x: int,
        y: int,
        cx: int,
        cy: int,
        badge: str,
        title: str,
        desc: str,
        accent_color: str = "38BDF8",
    ) -> str:
        badge_xml = ""
        if badge:
            badge_xml = (
                '<a:p>'
                f'<a:r><a:rPr lang="en-US" sz="1200" b="1"><a:solidFill><a:srgbClr val="{accent_color}"/></a:solidFill></a:rPr>'
                f'<a:t>{_escape(badge.upper())}</a:t></a:r>'
                '</a:p>'
            )

        title_xml = ""
        if title:
            title_xml = (
                '<a:p>'
                '<a:pPr spaceBefore="60000" spaceAfter="80000"/>'
                f'<a:r><a:rPr lang="en-US" sz="1900" b="1"><a:solidFill><a:srgbClr val="F8FAFC"/></a:solidFill></a:rPr>'
                f'<a:t>{_escape(title)}</a:t></a:r>'
                '</a:p>'
            )

        desc_xml = ""
        if desc:
            desc_xml = (
                '<a:p>'
                '<a:pPr spaceBefore="30000"/>'
                f'<a:r><a:rPr lang="en-US" sz="1400"><a:solidFill><a:srgbClr val="94A3B8"/></a:solidFill></a:rPr>'
                f'<a:t>{_escape(desc)}</a:t></a:r>'
                '</a:p>'
            )

        return (
            '<p:sp>'
            f'<p:nvSpPr><p:cNvPr id="{shape_id}" name="Card {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr>'
            f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 6000"/></a:avLst></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="161B26"/></a:solidFill>'
            f'<a:ln w="15000"><a:solidFill><a:srgbClr val="334155"/></a:solidFill></a:ln>'
            '</p:spPr>'
            f'<p:txBody><a:bodyPr tIns="254000" bIns="254000" lIns="254000" rIns="254000" anchor="t"/><a:lstStyle/>'
            f'{badge_xml}{title_xml}{desc_xml}'
            '</p:txBody>'
            '</p:sp>'
        )

    def _build_footer_shapes(self, base_id: int, slide_idx: int, total_slides: int) -> str:
        footer_line = (
            '<p:sp>'
            f'<p:nvSpPr><p:cNvPr id="{base_id}" name="Footer Line"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr>'
            '<a:xfrm><a:off x="838200" y="6300000"/><a:ext cx="10515600" cy="18000"/></a:xfrm>'
            '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
            '<a:solidFill><a:srgbClr val="1E293B"/></a:solidFill>'
            '</p:spPr>'
            '<p:txBody><a:bodyPr/><a:lstStyle/><a:p/></p:txBody>'
            '</p:sp>'
        )

        left_text = (
            '<p:sp>'
            f'<p:nvSpPr><p:cNvPr id="{base_id + 1}" name="Footer Left"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="838200" y="6380000"/><a:ext cx="6000000" cy="300000"/></a:xfrm></p:spPr>'
            '<p:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/>'
            '<a:p><a:r><a:rPr lang="en-US" sz="1000"><a:solidFill><a:srgbClr val="64748B"/></a:solidFill></a:rPr>'
            '<a:t>HINAA FRONTIER PRESENTATION STUDIO · CONFIDENTIAL</a:t></a:r></a:p>'
            '</p:txBody>'
            '</p:sp>'
        )

        right_text = (
            '<p:sp>'
            f'<p:nvSpPr><p:cNvPr id="{base_id + 2}" name="Footer Right"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            '<p:spPr><a:xfrm><a:off x="8353800" y="6380000"/><a:ext cx="3000000" cy="300000"/></a:xfrm></p:spPr>'
            '<p:txBody><a:bodyPr anchor="ctr"/><a:lstStyle/>'
            f'<a:p><a:pPr algn="r"/><a:r><a:rPr lang="en-US" sz="1000" b="1"><a:solidFill><a:srgbClr val="38BDF8"/></a:solidFill></a:rPr>'
            f'<a:t>SLIDE {slide_idx:02d} / {total_slides:02d}</a:t></a:r></a:p>'
            '</p:txBody>'
            '</p:sp>'
        )

        return f"{footer_line}\n{left_text}\n{right_text}"

    def _wrap_slide_tree(self, shapes_xml: str) -> str:
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">\n'
            '  <p:cSld>\n'
            '    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="0B0F19"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>\n'
            '    <p:spTree>\n'
            '      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>\n'
            '      <p:grpSpPr/>\n'
            f'      {shapes_xml}\n'
            '    </p:spTree>\n'
            '  </p:cSld>\n'
            '</p:sld>'
        )
