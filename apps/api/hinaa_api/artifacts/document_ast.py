"""Phase 14 — Universal Document Abstract Syntax Tree (AST).

Provides a format-neutral hierarchical representation of structured documents,
presentations, and spreadsheets with Markdown bidirectional parsing and inspection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ASTNodeType(str, Enum):
    DOCUMENT = "document"
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    INLINE_SPAN = "inline_span"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    CODE_BLOCK = "code_block"
    CALLOUT = "callout"
    IMAGE = "image"
    DIVIDER = "divider"
    PAGE_BREAK = "page_break"
    SLIDE = "slide"
    SHEET = "sheet"


class CalloutKind(str, Enum):
    NOTE = "NOTE"
    TIP = "TIP"
    IMPORTANT = "IMPORTANT"
    WARNING = "WARNING"
    CAUTION = "CAUTION"


@dataclass
class InlineSpan:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    strikethrough: bool = False
    link_url: str | None = None
    color: str | None = None


@dataclass
class ASTNode:
    node_type: ASTNodeType = ASTNodeType.DOCUMENT
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HeadingNode(ASTNode):
    level: int = 1
    text: str = ""
    spans: list[InlineSpan] = field(default_factory=list)
    anchor_id: str = ""

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.HEADING
        if not self.anchor_id and self.text:
            self.anchor_id = re.sub(r"[^a-z0-9]+", "-", self.text.lower()).strip("-")


@dataclass
class ParagraphNode(ASTNode):
    spans: list[InlineSpan] = field(default_factory=list)
    align: str = "left"  # left, center, right, justify

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.PARAGRAPH

    @property
    def plain_text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class ListItemNode(ASTNode):
    spans: list[InlineSpan] = field(default_factory=list)
    checked: bool | None = None  # None = bullet/number, True/False = task checkbox
    children: list[ASTNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.LIST_ITEM

    @property
    def plain_text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class ListNode(ASTNode):
    ordered: bool = False
    items: list[ListItemNode] = field(default_factory=list)
    start: int = 1

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.LIST


@dataclass
class TableCellNode(ASTNode):
    spans: list[InlineSpan] = field(default_factory=list)
    is_header: bool = False
    align: str = "left"  # left, center, right
    col_span: int = 1

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.TABLE_CELL

    @property
    def plain_text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class TableRowNode(ASTNode):
    cells: list[TableCellNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.TABLE_ROW


@dataclass
class TableNode(ASTNode):
    headers: TableRowNode | None = None
    rows: list[TableRowNode] = field(default_factory=list)
    caption: str = ""
    column_alignments: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.TABLE


@dataclass
class CodeBlockNode(ASTNode):
    code: str = ""
    language: str = ""
    caption: str = ""
    show_line_numbers: bool = False

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.CODE_BLOCK


@dataclass
class CalloutNode(ASTNode):
    kind: CalloutKind = CalloutKind.NOTE
    title: str = ""
    blocks: list[ASTNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.CALLOUT


@dataclass
class ImageNode(ASTNode):
    url: str = ""
    caption: str = ""
    alt_text: str = ""
    width: int | None = None
    height: int | None = None

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.IMAGE


@dataclass
class DividerNode(ASTNode):
    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.DIVIDER


@dataclass
class PageBreakNode(ASTNode):
    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.PAGE_BREAK


# Presentation extension nodes
@dataclass
class SlideNode(ASTNode):
    title: str = ""
    subtitle: str = ""
    bullets: list[str] = field(default_factory=list)
    speaker_notes: str = ""
    layout: str = "bullet"  # title, bullet, two_column, quote

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.SLIDE


# Spreadsheet extension nodes
@dataclass
class SheetNode(ASTNode):
    name: str = "Sheet1"
    headers: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.SHEET


@dataclass
class DocumentAST(ASTNode):
    """Universal Document AST Root."""
    title: str = "Untitled Document"
    author: str = "HINAA"
    subtitle: str = ""
    date: str = ""
    children: list[ASTNode] = field(default_factory=list)
    slides: list[SlideNode] = field(default_factory=list)
    sheets: list[SheetNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.node_type = ASTNodeType.DOCUMENT

    def get_headings(self) -> list[HeadingNode]:
        """Extract all headings for table-of-contents generation."""
        return [node for node in self.children if isinstance(node, HeadingNode)]

    def extract_plain_text(self) -> str:
        """Extract pure text representation across all blocks."""
        chunks: list[str] = []
        for child in self.children:
            if isinstance(child, HeadingNode):
                chunks.append(child.text)
            elif isinstance(child, ParagraphNode):
                chunks.append(child.plain_text)
            elif isinstance(child, ListNode):
                for item in child.items:
                    chunks.append(item.plain_text)
            elif isinstance(child, TableNode):
                if child.headers:
                    chunks.append(" | ".join(c.plain_text for c in child.headers.cells))
                for row in child.rows:
                    chunks.append(" | ".join(c.plain_text for c in row.cells))
            elif isinstance(child, CodeBlockNode):
                chunks.append(child.code)
            elif isinstance(child, CalloutNode):
                chunks.append(child.title)
                for b in child.blocks:
                    if isinstance(b, ParagraphNode):
                        chunks.append(b.plain_text)
        return "\n".join(chunks)


# ---------------------------------------------------------------------------
# Inline Markdown Parser Helper
# ---------------------------------------------------------------------------

def parse_inline_spans(text: str) -> list[InlineSpan]:
    """Parse Markdown inline styles (bold, italic, code, links, strikethrough)."""
    if not text:
        return []

    # Tokenizer pattern for inline syntax:
    # 1. Links: [text](url)
    # 2. Inline code: `code`
    # 3. Bold-italic: ***text***
    # 4. Bold: **text**
    # 5. Italic: *text* or _text_
    # 6. Strikethrough: ~~text~~
    pattern = re.compile(
        r"(\[(?P<link_text>[^\]]+)\]\((?P<link_url>[^\)]+)\))|"
        r"(`(?P<code>[^`]+)`)|"
        r"(\*\*\*(?P<bold_italic>[^\*]+)\*\*\*)|"
        r"(\*\*(?P<bold>[^\*]+)\*\*)|"
        r"(\*(?P<italic>[^\*]+)\*)|"
        r"(~~(?P<strike>[^~]+)~~)"
    )

    spans: list[InlineSpan] = []
    last_idx = 0

    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_idx:
            plain = text[last_idx:start]
            if plain:
                spans.append(InlineSpan(text=plain))

        if match.group("link_text"):
            spans.append(InlineSpan(
                text=match.group("link_text"),
                link_url=match.group("link_url"),
            ))
        elif match.group("code"):
            spans.append(InlineSpan(text=match.group("code"), code=True))
        elif match.group("bold_italic"):
            spans.append(InlineSpan(text=match.group("bold_italic"), bold=True, italic=True))
        elif match.group("bold"):
            spans.append(InlineSpan(text=match.group("bold"), bold=True))
        elif match.group("italic"):
            spans.append(InlineSpan(text=match.group("italic"), italic=True))
        elif match.group("strike"):
            spans.append(InlineSpan(text=match.group("strike"), strikethrough=True))

        last_idx = end

    if last_idx < len(text):
        trailing = text[last_idx:]
        if trailing:
            spans.append(InlineSpan(text=trailing))

    return spans or [InlineSpan(text=text)]


# ---------------------------------------------------------------------------
# DocumentParser (Markdown -> DocumentAST)
# ---------------------------------------------------------------------------

class DocumentParser:
    """Parses raw Markdown and GFM syntax into a structured DocumentAST."""

    CALLOUT_PATTERN = re.compile(r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](?:\s+(.*))?$", re.IGNORECASE)

    def parse(self, markdown_text: str, title: str | None = None) -> DocumentAST:
        lines = markdown_text.replace("\r\n", "\n").split("\n")
        doc = DocumentAST(title=title or "Document")
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            # 1. Blank line
            if not line.strip():
                i += 1
                continue

            # 2. Dividers / Thematic breaks
            if re.match(r"^(\*{3,}|-{3,}|_{3,})\s*$", line.strip()):
                doc.children.append(DividerNode())
                i += 1
                continue

            # 3. Fenced Code Block
            if line.strip().startswith("```"):
                fence_match = re.match(r"^```(\w*)", line.strip())
                lang = fence_match.group(1) if fence_match else ""
                i += 1
                code_lines: list[str] = []
                while i < n and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                if i < n and lines[i].strip().startswith("```"):
                    i += 1  # Skip closing fence
                doc.children.append(CodeBlockNode(code="\n".join(code_lines), language=lang))
                continue

            # 4. GitHub-style Callouts (> [!NOTE])
            callout_match = self.CALLOUT_PATTERN.match(line.strip())
            if callout_match:
                kind_str = callout_match.group(1).upper()
                custom_title = callout_match.group(2) or kind_str.capitalize()
                kind = CalloutKind(kind_str)
                callout_lines: list[str] = []
                i += 1
                while i < n and lines[i].strip().startswith(">"):
                    stripped = lines[i].strip()
                    content = stripped[1:].strip() if len(stripped) > 1 else ""
                    callout_lines.append(content)
                    i += 1

                callout_text = "\n".join(callout_lines)
                callout_node = CalloutNode(
                    kind=kind,
                    title=custom_title,
                    blocks=[ParagraphNode(spans=parse_inline_spans(callout_text))],
                )
                doc.children.append(callout_node)
                continue

            # 5. Headings (# ... ######)
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                h_text = heading_match.group(2).strip()
                if not doc.title or doc.title == "Document" and level == 1:
                    doc.title = h_text
                doc.children.append(HeadingNode(
                    level=level,
                    text=h_text,
                    spans=parse_inline_spans(h_text),
                ))
                i += 1
                continue

            # 6. Tables (| col1 | col2 | ...)
            if line.strip().startswith("|") and line.strip().endswith("|"):
                table_lines: list[str] = []
                while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1
                table_node = self._parse_table(table_lines)
                if table_node:
                    doc.children.append(table_node)
                continue

            # 7. Lists (ordered or unordered, including checkboxes)
            list_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", line)
            if list_match:
                list_lines: list[str] = []
                while i < n and re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[i]):
                    list_lines.append(lines[i])
                    i += 1
                list_node = self._parse_list(list_lines)
                if list_node:
                    doc.children.append(list_node)
                continue

            # 8. Regular paragraph
            p_lines: list[str] = []
            while (
                i < n
                and lines[i].strip()
                and not lines[i].strip().startswith("#")
                and not lines[i].strip().startswith("```")
                and not lines[i].strip().startswith(">")
                and not (lines[i].strip().startswith("|") and lines[i].strip().endswith("|"))
                and not re.match(r"^(\s*)([-*+]|\d+\.)\s+", lines[i])
                and not re.match(r"^(\*{3,}|-{3,}|_{3,})\s*$", lines[i].strip())
            ):
                p_lines.append(lines[i].strip())
                i += 1

            p_text = " ".join(p_lines)
            if p_text:
                doc.children.append(ParagraphNode(spans=parse_inline_spans(p_text)))

        return doc

    @staticmethod
    def _parse_table(lines: list[str]) -> TableNode | None:
        if len(lines) < 2:
            return None

        def split_row(r: str) -> list[str]:
            raw_cells = r.strip("|").split("|")
            return [c.strip() for c in raw_cells]

        header_cells = split_row(lines[0])
        # Check if line 1 is separator (--- | :---: | ---:)
        alignments: list[str] = []
        sep_row = split_row(lines[1])
        has_sep = False
        if all(re.match(r"^:?-+:?$", s) for s in sep_row if s):
            has_sep = True
            for s in sep_row:
                if s.startswith(":") and s.endswith(":"):
                    alignments.append("center")
                elif s.endswith(":"):
                    alignments.append("right")
                else:
                    alignments.append("left")

        headers = TableRowNode(cells=[
            TableCellNode(spans=parse_inline_spans(c), is_header=True)
            for c in header_cells
        ])

        data_start = 2 if has_sep else 1
        rows: list[TableRowNode] = []
        for line in lines[data_start:]:
            cells = split_row(line)
            rows.append(TableRowNode(cells=[
                TableCellNode(spans=parse_inline_spans(c))
                for c in cells
            ]))

        return TableNode(headers=headers, rows=rows, column_alignments=alignments)

    @staticmethod
    def _parse_list(lines: list[str]) -> ListNode | None:
        if not lines:
            return None

        first = lines[0].lstrip()
        ordered = bool(re.match(r"^\d+\.", first))
        items: list[ListItemNode] = []

        for l in lines:
            m = re.match(r"^\s*([-*+]|\d+\.)\s+(.*)$", l)
            if not m:
                continue
            content = m.group(2).strip()

            # Task list check: [ ] or [x]
            checked = None
            if content.startswith("[ ] "):
                checked = False
                content = content[4:].strip()
            elif content.lower().startswith("[x] "):
                checked = True
                content = content[4:].strip()

            items.append(ListItemNode(
                spans=parse_inline_spans(content),
                checked=checked,
            ))

        return ListNode(ordered=ordered, items=items)
