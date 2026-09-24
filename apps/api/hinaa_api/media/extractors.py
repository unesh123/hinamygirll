from __future__ import annotations

import csv
import io
import logging
import zipfile
import xml.etree.ElementTree as ET

logger = logging.getLogger("hinaa.media.extractors")


def extract_csv_summary(raw_bytes: bytes, max_rows: int = 50) -> str:
    """Parses CSV bytes, extracts column headers, total rows, and formatted preview table."""
    try:
        # Detect encoding: utf-8 first, fallback to latin-1
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1", errors="replace")

        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return "CSV Document: Empty file."

        headers = rows[0]
        data_rows = rows[1:]
        total_rows = len(data_rows)
        col_count = len(headers)

        lines = [
            f"CSV Document Summary:",
            f"- Columns ({col_count}): {', '.join(headers)}",
            f"- Total Data Rows: {total_rows}",
            "",
            "Data Preview (First rows):",
        ]

        # Format header row
        lines.append(" | ".join(str(h) for h in headers))
        lines.append(" | ".join(["---"] * max(col_count, 1)))

        for row in data_rows[:max_rows]:
            padded = row + [""] * (col_count - len(row))
            lines.append(" | ".join(str(c)[:50] for c in padded[:col_count]))

        if total_rows > max_rows:
            lines.append(f"... ({total_rows - max_rows} additional rows omitted)")

        return "\n".join(lines)
    except Exception as err:
        logger.warning("Failed to extract CSV summary: %s", err)
        return f"CSV Document: Unable to fully parse CSV ({str(err)})."


def extract_xlsx_summary(raw_bytes: bytes, max_rows: int = 50) -> str:
    """Safely extracts sheets and cell data from XLSX bytes using standard zipfile and xml parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in zf.namelist():
                ss_xml = zf.read("xl/sharedStrings.xml")
                root = ET.fromstring(ss_xml)
                ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in root.findall(".//main:t", ns):
                    shared_strings.append(si.text or "")
                if not shared_strings:
                    for elem in root.iter():
                        if elem.tag.endswith("}t") and elem.text:
                            shared_strings.append(elem.text)

            sheet_names = [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            if not sheet_names:
                return "Excel Spreadsheet: No worksheets found."

            sheet_xml = zf.read(sheet_names[0])
            root = ET.fromstring(sheet_xml)

            rows: list[list[str]] = []
            for row_elem in root.iter():
                if row_elem.tag.endswith("}row"):
                    current_row: list[str] = []
                    for c_elem in row_elem.iter():
                        if c_elem.tag.endswith("}c"):
                            cell_type = c_elem.attrib.get("t")
                            v_elem = None
                            for child in c_elem:
                                if child.tag.endswith("}v"):
                                    v_elem = child
                                    break
                            val = ""
                            if v_elem is not None and v_elem.text:
                                raw_v = v_elem.text
                                if cell_type == "s" and raw_v.isdigit():
                                    idx = int(raw_v)
                                    val = shared_strings[idx] if idx < len(shared_strings) else raw_v
                                else:
                                    val = raw_v
                            current_row.append(val)
                    if any(current_row):
                        rows.append(current_row)

            if not rows:
                return "Excel Spreadsheet: Empty sheet."

            headers = rows[0]
            col_count = len(headers)
            data_rows = rows[1:]

            lines = [
                f"Excel Spreadsheet Summary (Sheet 1):",
                f"- Columns ({col_count}): {', '.join(str(h) for h in headers if h)}",
                f"- Data Rows: {len(data_rows)}",
                "",
                "Preview:",
            ]
            lines.append(" | ".join(str(h) for h in headers))
            lines.append(" | ".join(["---"] * max(col_count, 1)))
            for r in data_rows[:max_rows]:
                lines.append(" | ".join(str(c)[:50] for c in r))

            if len(data_rows) > max_rows:
                lines.append(f"... ({len(data_rows) - max_rows} additional rows omitted)")

            return "\n".join(lines)
    except Exception as err:
        logger.warning("Failed to extract XLSX summary: %s", err)
        return f"Excel Spreadsheet: Unable to parse binary sheet ({str(err)})."


def extract_docx_text(raw_bytes: bytes, max_chars: int = 8000) -> str:
    """Extracts clean paragraph text from DOCX bytes using standard zipfile and xml parsing."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            if "word/document.xml" not in zf.namelist():
                return "Word Document: No document text found."

            doc_xml = zf.read("word/document.xml")
            root = ET.fromstring(doc_xml)

            paragraphs: list[str] = []
            for p in root.iter():
                if p.tag.endswith("}p"):
                    texts: list[str] = []
                    for t in p.iter():
                        if t.tag.endswith("}t") and t.text:
                            texts.append(t.text)
                    para_text = "".join(texts).strip()
                    if para_text:
                        paragraphs.append(para_text)

            full_text = "\n\n".join(paragraphs)
            if not full_text:
                return "Word Document: Empty document."

            if len(full_text) > max_chars:
                return full_text[:max_chars] + f"\n\n[... truncated {len(full_text) - max_chars} characters]"
            return full_text
    except Exception as err:
        logger.warning("Failed to extract DOCX text: %s", err)
        return f"Word Document: Unable to parse document ({str(err)})."


def inspect_zip_archive(raw_bytes: bytes, max_entries: int = 100) -> str:
    """Safely inspects a ZIP archive file tree and uncompressed sizes without extraction."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            infolist = zf.infolist()
            total_files = len(infolist)
            total_uncompressed = sum(info.file_size for info in infolist)

            lines = [
                f"ZIP Archive Inspection (Safe Manifest):",
                f"- Total Items: {total_files}",
                f"- Total Uncompressed Size: {total_uncompressed / (1024 * 1024):.2f} MB",
                "",
                "Archive Contents:",
            ]

            for info in infolist[:max_entries]:
                is_dir = info.is_dir()
                tag = "[DIR]" if is_dir else f"[{info.file_size} bytes]"
                lines.append(f"  {tag} {info.filename}")

            if total_files > max_entries:
                lines.append(f"  ... ({total_files - max_entries} additional items omitted)")

            return "\n".join(lines)
    except Exception as err:
        logger.warning("Failed to inspect ZIP archive: %s", err)
        return f"ZIP Archive: Invalid or corrupted archive ({str(err)})."


def extract_text_document(raw_bytes: bytes, max_chars: int = 10000) -> str:
    """Decodes plain text or markdown document bytes safely."""
    try:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1", errors="replace")

        if len(text) > max_chars:
            return text[:max_chars] + f"\n\n[... truncated {len(text) - max_chars} characters]"
        return text
    except Exception as err:
        return f"Text Document: Unable to decode ({str(err)})."
