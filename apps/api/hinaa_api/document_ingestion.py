from __future__ import annotations

import re
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


MAX_EXTRACTED_CHARS = 80_000
MAX_ARCHIVE_EXPANDED_BYTES = 30 * 1024 * 1024
_TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml", ".toml",
    ".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".sql", ".log",
}


@dataclass(frozen=True)
class DocumentExtraction:
    parser: str
    kind: str
    text: str
    char_count: int
    truncated: bool


def _bounded_text(value: str) -> tuple[str, bool]:
    cleaned = re.sub(r"\r\n?", "\n", value).strip()
    if len(cleaned) <= MAX_EXTRACTED_CHARS:
        return cleaned, False
    return cleaned[:MAX_EXTRACTED_CHARS].rstrip() + "\n\n[HINAA: local preview truncated]", True


def _archive_xml_text(path: Path, candidates: list[str], parser: str, kind: str) -> DocumentExtraction:
    with zipfile.ZipFile(path) as archive:
        info = archive.infolist()
        expanded = sum(item.file_size for item in info)
        if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
            raise ValueError("The document expands beyond HINAA's 30 MB local extraction limit.")
        chunks: list[str] = []
        for name in candidates:
            try:
                raw = archive.read(name)
            except KeyError:
                continue
            try:
                root = ElementTree.fromstring(raw)
                text = " ".join(piece.strip() for piece in root.itertext() if piece and piece.strip())
            except ElementTree.ParseError:
                text = re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="replace"))
            if text:
                chunks.append(text)
    bounded, truncated = _bounded_text("\n\n".join(chunks))
    if not bounded:
        raise ValueError("No readable text was found in this document.")
    return DocumentExtraction(parser=parser, kind=kind, text=bounded, char_count=len(bounded), truncated=truncated)


def extract_local_document(path: Path, name: str | None = None) -> DocumentExtraction:
    """Extract bounded local text without executing or following document content."""
    suffix = Path(name or path.name).suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        bounded, truncated = _bounded_text(path.read_text(encoding="utf-8", errors="replace"))
        if not bounded:
            raise ValueError("The text file is empty.")
        return DocumentExtraction(parser="utf-8-text", kind="text", text=bounded, char_count=len(bounded), truncated=truncated)

    if suffix == ".pdf":
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                check=False,
                capture_output=True,
                timeout=25,
            )
        except FileNotFoundError as error:
            raise RuntimeError("PDF reading is not installed in this local HINAA runtime.") from error
        except subprocess.TimeoutExpired as error:
            raise TimeoutError("PDF extraction exceeded HINAA's 25-second local limit.") from error
        if result.returncode != 0:
            raise ValueError("This PDF could not be read as selectable text. It may be scanned or protected.")
        bounded, truncated = _bounded_text(result.stdout.decode("utf-8", errors="replace"))
        if not bounded:
            raise ValueError("No selectable text was found in this PDF. Upload an OCR-ready PDF or paste the relevant page text.")
        return DocumentExtraction(parser="pdftotext", kind="pdf", text=bounded, char_count=len(bounded), truncated=truncated)

    if suffix == ".docx":
        return _archive_xml_text(path, ["word/document.xml"], "docx-xml", "docx")

    if suffix == ".pptx":
        with zipfile.ZipFile(path) as archive:
            candidates = sorted(name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
        return _archive_xml_text(path, candidates, "pptx-xml", "pptx")

    raise ValueError("Supported local analysis formats are TXT, Markdown, CSV, JSON, PDF, DOCX, and PPTX.")
