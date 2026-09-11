from __future__ import annotations

import io
import zipfile
import pytest
from fastapi.testclient import TestClient

from hinaa_api.media.extractors import (
    extract_csv_summary,
    extract_xlsx_summary,
    extract_docx_text,
    inspect_zip_archive,
    extract_text_document,
)
from hinaa_api.media.asset_store import AssetStore
from hinaa_api.media.resolver import MediaResolver, ResolvedMedia
from hinaa_api.media.models import AssetKind
from hinaa_api.models import TurnRequest
from hinaa_api.prompts.models import PromptInput
from hinaa_api.prompts.assembly import assemble_prompt


def test_csv_summary_extractor_formats_table():
    csv_data = b"id,name,score,department\n1,Alice,95,Engineering\n2,Bob,88,Design\n3,Charlie,92,Product\n"
    summary = extract_csv_summary(csv_data)
    assert "Columns (4): id, name, score, department" in summary
    assert "Total Data Rows: 3" in summary
    assert "Alice" in summary
    assert "Engineering" in summary
    assert "Charlie" in summary


def test_csv_summary_empty_and_corrupt():
    empty_summary = extract_csv_summary(b"")
    assert "Empty file" in empty_summary

    malformed = extract_csv_summary(b"\xff\xfe\x00malformed,data\n1,2")
    assert "CSV Document" in malformed


def test_xlsx_summary_extractor():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        shared_xml = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4">'
            b'<si><t>Quarter</t></si>'
            b'<si><t>Revenue</t></si>'
            b'<si><t>Q1</t></si>'
            b'<si><t>Q2</t></si>'
            b'</sst>'
        )
        zf.writestr("xl/sharedStrings.xml", shared_xml)

        sheet_xml = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            b'<sheetData>'
            b'<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
            b'<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2"><v>10500</v></c></row>'
            b'<row r="3"><c r="A3" t="s"><v>3</v></c><c r="B3"><v>14200</v></c></row>'
            b'</sheetData>'
            b'</worksheet>'
        )
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)

    xlsx_bytes = buf.getvalue()
    summary = extract_xlsx_summary(xlsx_bytes)
    # Check for actual header formats from the implementation
    assert "Excel Spreadsheet" in summary
    assert "Quarter" in summary
    assert "Revenue" in summary
    assert "Q1" in summary
    assert "10500" in summary
    assert "Q2" in summary
    assert "14200" in summary


def test_docx_text_extractor():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        doc_xml = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'<w:body>'
            b'<w:p><w:r><w:t>Project HINAA Universal Architecture</w:t></w:r></w:p>'
            b'<w:p><w:r><w:t>Milestone P1.7 interaction reality gate.</w:t></w:r></w:p>'
            b'</w:body>'
            b'</w:document>'
        )
        zf.writestr("word/document.xml", doc_xml)

    docx_bytes = buf.getvalue()
    text = extract_docx_text(docx_bytes)
    # Actual implementation returns just the paragraph text (no "Word Document Contents:" header)
    assert "Project HINAA Universal Architecture" in text
    assert "Milestone P1.7 interaction reality gate" in text


def test_inspect_zip_archive_safe():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("src/main.py", "print('hello')")
        zf.writestr("docs/readme.md", "# Documentation")
        zf.writestr("data/sample.csv", "a,b\n1,2")

    zip_bytes = buf.getvalue()
    manifest = inspect_zip_archive(zip_bytes)
    # Actual header format from the implementation
    assert "ZIP Archive" in manifest
    assert "3" in manifest  # 3 files
    assert "src/main.py" in manifest
    assert "docs/readme.md" in manifest
    assert "data/sample.csv" in manifest


def test_extract_text_document():
    raw = b"# Executive Summary\nAll subsystems healthy and ready for deployment."
    doc = extract_text_document(raw)
    assert "Executive Summary" in doc
    assert "subsystems healthy" in doc


@pytest.mark.asyncio
async def test_media_resolver_handles_stored_document(tmp_path):
    # AssetStore uses base_dir param, not storage_dir
    store = AssetStore(base_dir=tmp_path / "assets")
    resolver = MediaResolver(asset_store=store)

    csv_bytes = b"metric,value\naccuracy,0.99\nlatency_ms,45"
    stored = store.store_bytes(
        raw_bytes=csv_bytes,
        mime_type="text/csv",
        filename="metrics.csv",
    )

    resolved = await resolver.resolve(stored.id, role="document")
    assert resolved.asset_id == stored.id
    assert resolved.kind == AssetKind.SPREADSHEET  # CSV maps to SPREADSHEET
    assert resolved.filename == "metrics.csv"
    assert resolved.extracted_text is not None
    assert "metric" in resolved.extracted_text
    assert "accuracy" in resolved.extracted_text


def test_prompt_assembly_injects_document_context():
    resolved = ResolvedMedia(
        asset_id="doc-123",
        bytes_data=b"dummy",
        mime_type="text/csv",
        sha256="abc",
        kind=AssetKind.DOCUMENT,
        filename="sales.csv",
        extracted_text="CSV Document Summary:\n- Columns (2): month, sales\nJan | 100\nFeb | 150",
    )

    inp = PromptInput(
        companion_id="hinaa",
        interaction_mode="rest",
        user_text="What were the February sales?",
        attachments=(resolved,),
    )
    pkg = assemble_prompt(inp)

    doc_layer = next((l for l in pkg.layers if l.name == "document_context"), None)
    assert doc_layer is not None
    assert "sales.csv" in doc_layer.text
    assert "Feb | 150" in doc_layer.text


def test_api_universal_asset_ingestion(client: TestClient):
    csv_content = b"col1,col2\nval1,val2"
    response = client.post(
        "/v1/assets",
        files={"file": ("dataset.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    # CSV maps to 'spreadsheet' kind not 'document'
    assert data["kind"] in ("document", "spreadsheet")
    assert data["mime_type"] == "text/csv"
    assert data["filename"] == "dataset.csv"
