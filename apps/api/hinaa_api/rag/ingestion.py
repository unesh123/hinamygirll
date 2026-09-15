from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


@dataclass
class ChunkMetadata:
    document_id: str
    source: str
    page: int | None = None
    section_path: list[str] = field(default_factory=list)
    chunk_index: int = 0
    token_count: int = 0
    content_hash: str = ""
    is_code: bool = False
    code_language: str | None = None
    is_table: bool = False
    visibility: str = "public"  # public, internal, user_only
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "source": self.source,
            "page": self.page,
            "section_path": self.section_path,
            "chunk_index": self.chunk_index,
            "token_count": self.token_count,
            "content_hash": self.content_hash,
            "is_code": self.is_code,
            "code_language": self.code_language,
            "is_table": self.is_table,
            "visibility": self.visibility,
            "version": self.version,
            "created_at": self.created_at,
        }


@dataclass
class StructuredChunk:
    chunk_id: str
    text: str
    metadata: ChunkMetadata

    @property
    def section_title(self) -> str:
        return " > ".join(self.metadata.section_path) if self.metadata.section_path else "General"


class StructuredChunker:
    """Structured chunker for RAG v2.

    Preserves page boundaries, document section hierarchies, markdown/HTML tables,
    and fenced code blocks without breaking semantic continuity.
    """

    def __init__(
        self,
        target_chunk_tokens: int = 300,
        overlap_tokens: int = 40,
        max_chunk_tokens: int = 600,
    ) -> None:
        self.target_chunk_tokens = max(50, target_chunk_tokens)
        self.overlap_tokens = max(0, min(overlap_tokens, target_chunk_tokens // 2))
        self.max_chunk_tokens = max(self.target_chunk_tokens, max_chunk_tokens)

    def chunk(
        self,
        text: str,
        *,
        document_id: str = "doc_default",
        source: str = "source",
        page: int | None = None,
        visibility: str = "public",
        version: str = "1.0",
    ) -> list[StructuredChunk]:
        raw = text.replace("\r\n", "\n").strip()
        if not raw:
            return []

        # Step 1: Parse content into typed blocks
        blocks = self._parse_blocks(raw)

        # Step 2: Assemble blocks into chunks observing token limits and boundaries
        chunks: list[StructuredChunk] = []
        current_pieces: list[str] = []
        current_tokens = 0
        current_section: list[str] = []
        current_is_code = False
        current_code_lang: str | None = None
        current_is_table = False
        chunk_idx = 0

        def flush_chunk():
            nonlocal chunk_idx, current_pieces, current_tokens, current_is_code, current_code_lang, current_is_table
            if not current_pieces:
                return
            combined_text = "\n\n".join(current_pieces).strip()
            if not combined_text:
                current_pieces = []
                current_tokens = 0
                return

            ch_hash = hashlib.sha256(combined_text.encode("utf-8")).hexdigest()
            meta = ChunkMetadata(
                document_id=document_id,
                source=source,
                page=page,
                section_path=list(current_section),
                chunk_index=chunk_idx,
                token_count=estimate_tokens(combined_text),
                content_hash=ch_hash,
                is_code=current_is_code,
                code_language=current_code_lang,
                is_table=current_is_table,
                visibility=visibility,
                version=version,
            )
            chunks.append(
                StructuredChunk(
                    chunk_id=f"{document_id}_{chunk_idx}_{ch_hash[:8]}",
                    text=combined_text,
                    metadata=meta,
                )
            )
            chunk_idx += 1
            current_pieces = []
            current_tokens = 0
            current_is_code = False
            current_code_lang = None
            current_is_table = False

        for b_type, b_content, b_meta in blocks:
            b_tok = estimate_tokens(b_content)

            if b_type == "heading":
                # Flush existing chunk before changing major section
                if current_tokens >= (self.target_chunk_tokens // 2):
                    flush_chunk()
                heading_level = b_meta.get("level", 1)
                heading_title = b_meta.get("title", b_content.lstrip("#").strip())
                # Update section hierarchy
                while len(current_section) >= heading_level:
                    current_section.pop()
                current_section.append(heading_title)
                current_pieces.append(b_content)
                current_tokens += b_tok
                continue

            if b_type == "table":
                if current_tokens + b_tok > self.max_chunk_tokens and current_pieces:
                    flush_chunk()
                current_pieces.append(b_content)
                current_tokens += b_tok
                current_is_table = True
                if current_tokens >= self.target_chunk_tokens:
                    flush_chunk()
                continue

            if b_type == "code":
                if current_tokens + b_tok > self.max_chunk_tokens and current_pieces:
                    flush_chunk()
                current_pieces.append(b_content)
                current_tokens += b_tok
                current_is_code = True
                current_code_lang = b_meta.get("language")
                if current_tokens >= self.target_chunk_tokens:
                    flush_chunk()
                continue

            # Standard prose/paragraphs
            if b_tok > self.max_chunk_tokens:
                # Paragraph itself is too large, split by sentences
                sentences = self._split_sentences(b_content)
                for sentence in sentences:
                    s_tok = estimate_tokens(sentence)
                    if current_tokens + s_tok > self.target_chunk_tokens and current_pieces:
                        flush_chunk()
                    current_pieces.append(sentence)
                    current_tokens += s_tok
            else:
                if current_tokens + b_tok > self.target_chunk_tokens and current_pieces:
                    flush_chunk()
                current_pieces.append(b_content)
                current_tokens += b_tok

        flush_chunk()
        return chunks

    def _parse_blocks(self, text: str) -> list[tuple[str, str, dict[str, Any]]]:
        """Classify text into typed contiguous units."""
        lines = text.split("\n")
        blocks: list[tuple[str, str, dict[str, Any]]] = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            # 1. Heading
            heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                blocks.append(("heading", line, {"level": level, "title": title}))
                i += 1
                continue

            # 2. Code fence
            code_match = re.match(r"^```(\w*)", line.strip())
            if code_match:
                lang = code_match.group(1) or None
                code_lines = [line]
                i += 1
                while i < n:
                    code_lines.append(lines[i])
                    if lines[i].strip().startswith("```"):
                        i += 1
                        break
                    i += 1
                blocks.append(("code", "\n".join(code_lines), {"language": lang}))
                continue

            # 3. Table detection (markdown pipe table)
            if "|" in line and (line.strip().startswith("|") or line.strip().endswith("|")):
                table_lines = [line]
                i += 1
                while i < n and "|" in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                blocks.append(("table", "\n".join(table_lines), {}))
                continue

            # 4. Normal paragraph accumulation
            para_lines = [line]
            i += 1
            while i < n:
                next_line = lines[i]
                if not next_line.strip():
                    break
                if re.match(r"^#{1,6}\s+", next_line) or next_line.strip().startswith("```") or (
                    "|" in next_line and (next_line.strip().startswith("|") or next_line.strip().endswith("|"))
                ):
                    break
                para_lines.append(next_line)
                i += 1

            p_text = "\n".join(para_lines).strip()
            if p_text:
                blocks.append(("prose", p_text, {}))
            # skip trailing blank lines
            while i < n and not lines[i].strip():
                i += 1

        return blocks

    def _split_sentences(self, text: str) -> list[str]:
        # Split on sentence terminals followed by space
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]
