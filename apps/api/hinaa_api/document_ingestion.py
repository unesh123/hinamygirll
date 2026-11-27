from __future__ import annotations

import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 80_000
MAX_ARCHIVE_EXPANDED_BYTES = 30 * 1024 * 1024
_TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".mdx", ".rst", ".csv", ".tsv", ".json", ".jsonl",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".py", ".ts", ".tsx",
    ".js", ".jsx", ".mjs", ".cjs", ".html", ".htm", ".css", ".scss", ".sass", ".sql",
    ".graphql", ".prisma", ".sh", ".bash", ".ps1", ".bat", ".go", ".rs", ".java",
    ".kt", ".swift", ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".vue", ".svelte",
    ".astro", ".xml", ".svg", ".log", ".gitignore", ".dockerignore",
}
_TEXT_BASENAMES = frozenset({"readme", "license", "dockerfile", "makefile", "procfile", ".env.example"})


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
    base = Path(name or path.name).name.lower()
    suffix = Path(name or path.name).suffix.lower()
    if suffix in _TEXT_SUFFIXES or base in _TEXT_BASENAMES:
        bounded, truncated = _bounded_text(path.read_text(encoding="utf-8", errors="replace"))
        if not bounded:
            raise ValueError("The text file is empty.")
        return DocumentExtraction(parser="utf-8-text", kind="text", text=bounded, char_count=len(bounded), truncated=truncated)

    if suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages_text = []
            for idx, page in enumerate(reader.pages):
                txt = page.extract_text()
                if txt and txt.strip():
                    pages_text.append(f"--- Page {idx + 1} ---\n{txt.strip()}")
            if pages_text:
                full_text = "\n\n".join(pages_text)
                bounded, truncated = _bounded_text(full_text)
                return DocumentExtraction(
                    parser="pypdf",
                    kind="pdf",
                    text=bounded,
                    char_count=len(bounded),
                    truncated=truncated,
                )
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                check=False,
                capture_output=True,
                timeout=25,
            )
            if result.returncode == 0:
                bounded, truncated = _bounded_text(result.stdout.decode("utf-8", errors="replace"))
                if bounded:
                    return DocumentExtraction(
                        parser="pdftotext",
                        kind="pdf",
                        text=bounded,
                        char_count=len(bounded),
                        truncated=truncated,
                    )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        raise ValueError("No selectable text could be extracted from this PDF. It may be scanned or image-only.")

    if suffix == ".docx":
        return _archive_xml_text(path, ["word/document.xml"], "docx-xml", "docx")

    if suffix == ".pptx":
        with zipfile.ZipFile(path) as archive:
            candidates = sorted(name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
        return _archive_xml_text(path, candidates, "pptx-xml", "pptx")

    if suffix == ".xlsx":
        from .media.extractors import extract_xlsx_summary
        bounded, truncated = _bounded_text(extract_xlsx_summary(path.read_bytes(), max_rows=200))
        if not bounded:
            raise ValueError("The spreadsheet is empty.")
        return DocumentExtraction(parser="xlsx-xml", kind="xlsx", text=bounded, char_count=len(bounded), truncated=truncated)

    if suffix == ".zip":
        from .media.extractors import inspect_zip_archive
        bounded, truncated = _bounded_text(inspect_zip_archive(path.read_bytes(), max_entries=160, include_previews=True))
        if not bounded:
            raise ValueError("The ZIP archive is empty.")
        return DocumentExtraction(parser="zip-inspect", kind="zip", text=bounded, char_count=len(bounded), truncated=truncated)

    # Fallback: safe UTF-8 inspection for arbitrary text/config files before rejecting binary/media blobs
    _NON_DOCUMENT_MEDIA_EXTS = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tiff", ".tif", ".avif",
        ".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".mpeg", ".mpg",
        ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".exe", ".dll", ".so", ".dylib", ".bin",
    }
    if suffix not in _NON_DOCUMENT_MEDIA_EXTS:
        raw_head = path.read_bytes()[:8192]
        if b"\x00" not in raw_head:
            try:
                decoded = path.read_bytes().decode("utf-8")
                bounded, truncated = _bounded_text(decoded)
                if bounded:
                    return DocumentExtraction(parser="utf-8-fallback", kind="text", text=bounded, char_count=len(bounded), truncated=truncated)
            except UnicodeDecodeError:
                pass

    raise ValueError("Supported analysis formats include text, Markdown, code files, PDF, DOCX, PPTX, XLSX, and ZIP.")


def extract_uploaded_document(raw_bytes: bytes, filename: str | None) -> DocumentExtraction:
    """Use a disposable, server-owned path; never interpolate client paths."""
    if not raw_bytes:
        raise ValueError("The document is empty.")
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("Document exceeds the 10 MiB upload limit.")
    safe_name = (filename or "document.txt").replace("\\", "/").rsplit("/", 1)[-1]
    base_lower = safe_name.lower()
    suffix = Path(safe_name).suffix.lower() or ".txt"
    supported_archive_docs = {".pdf", ".docx", ".pptx", ".xlsx", ".zip"}
    non_doc_media_exts = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".tiff", ".tif", ".avif",
        ".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v", ".mpeg", ".mpg",
        ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".exe", ".dll", ".so", ".dylib", ".bin",
    }
    is_utf8_text = (suffix not in non_doc_media_exts) and (b"\x00" not in raw_bytes[:8192])
    if (
        suffix in non_doc_media_exts
        or (
            base_lower not in _TEXT_BASENAMES
            and suffix not in (_TEXT_SUFFIXES | supported_archive_docs)
            and not is_utf8_text
        )
    ):
        raise ValueError("Supported analysis formats are text, Markdown, code, PDF, DOCX, PPTX, XLSX, and ZIP.")
    with tempfile.TemporaryDirectory(prefix="hinaa-document-") as directory:
        path = Path(directory) / f"document{suffix}"
        path.write_bytes(raw_bytes)
        result = extract_local_document(path, safe_name)
        if not result.text.strip():
            raise ValueError("No readable text was found in this document.")
        return result
