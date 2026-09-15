"""Phase 14 — Artifact OS Comprehensive Test Suite.

Deterministic tests covering:
1. Artifact models & checksums
2. Document AST & GFM Parser
3. Multi-format Exporters (MD, HTML, DOCX, PPTX, XLSX, PDF)
4. Archive Packager & Zip-Slip Security
5. Render & Inspect Telemetry & Document Linting
6. Unified ArtifactService Workflows
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
import pytest

from hinaa_api.artifacts import (
    ArchivePackager,
    ArchiveSecurityError,
    ArtifactFormat,
    ArtifactInspector,
    ArtifactRecord,
    ArtifactService,
    ArtifactStatus,
    ArtifactType,
    CalloutKind,
    DocxExporter,
    DocumentAST,
    DocumentParser,
    HeadingNode,
    HtmlExporter,
    LintSeverity,
    MarkdownExporter,
    PdfExporter,
    PptxExporter,
    XlsxExporter,
    parse_inline_spans,
)


SAMPLE_MARKDOWN = """# Autonomous Architecture Dossier

Welcome to the comprehensive HINAA engineering specification.

## Core Directives

- Fast, low-latency companion streaming
- [x] Integrate Response AST v2
- [ ] Implement multi-agent consensus

> [!NOTE] System Invariant
> State must always be durably persisted before execution completes.

> [!WARNING] Performance Alert
> High-frame avatars require steady clock synchronisation.

### Telemetry Matrix

| Metric | Target | Verified | Status |
| :--- | :---: | :---: | ---: |
| Latency | < 50ms | 38ms | Nominal |
| Audio Clock Drift | 0ms | 0ms | Pass |

### Implementation Code

```python
def execute_safe_turn(turn_id: str) -> bool:
    return True
```

---
"""


# ---------------------------------------------------------------------------
# 1. Models & Hashes
# ---------------------------------------------------------------------------

class TestArtifactModels:
    def test_artifact_record_hash_and_size(self):
        record = ArtifactRecord(
            user_id="user_123",
            title="Design Doc",
            filename="design.md",
            content="# Hello World",
            format=ArtifactFormat.MD,
        )
        record.compute_hash_and_size()

        assert record.size_bytes == 13
        assert len(record.sha256) == 64
        assert record.get_mime_type() == "text/markdown; charset=utf-8"
        assert record.status == ArtifactStatus.VERIFIED

    def test_binary_content_hash(self):
        data = b"\x00\x01\x02\x03\x04"
        record = ArtifactRecord(
            user_id="user_123",
            title="Binary Asset",
            filename="asset.bin",
            content=data,
            format=ArtifactFormat.ZIP,
        )
        record.compute_hash_and_size()
        assert record.size_bytes == 5
        assert record.get_mime_type() == "application/zip"


# ---------------------------------------------------------------------------
# 2. Document AST & Parser
# ---------------------------------------------------------------------------

class TestDocumentASTAndParser:
    def test_parse_inline_spans(self):
        text = "Normal **bold** and *italic* with `code` and [link](https://hinaa.ai)"
        spans = parse_inline_spans(text)
        assert any(s.bold for s in spans)
        assert any(s.italic for s in spans)
        assert any(s.code for s in spans)
        assert any(s.link_url == "https://hinaa.ai" for s in spans)

    def test_parse_document_structure(self):
        parser = DocumentParser()
        doc = parser.parse(SAMPLE_MARKDOWN, title="Architecture Dossier")

        assert doc.title == "Architecture Dossier"
        headings = doc.get_headings()
        assert len(headings) >= 3
        assert headings[0].text == "Autonomous Architecture Dossier"
        assert headings[1].text == "Core Directives"
        assert headings[2].text == "Telemetry Matrix"

        plain = doc.extract_plain_text()
        assert "Autonomous Architecture Dossier" in plain
        assert "System Invariant" in plain
        assert "execute_safe_turn" in plain

    def test_parse_tables_and_callouts(self):
        parser = DocumentParser()
        doc = parser.parse(SAMPLE_MARKDOWN)

        from hinaa_api.artifacts.document_ast import CalloutNode, TableNode
        callouts = [n for n in doc.children if isinstance(n, CalloutNode)]
        assert len(callouts) == 2
        assert callouts[0].kind == CalloutKind.NOTE
        assert callouts[0].title == "System Invariant"
        assert callouts[1].kind == CalloutKind.WARNING

        tables = [n for n in doc.children if isinstance(n, TableNode)]
        assert len(tables) == 1
        assert len(tables[0].rows) == 2
        assert len(tables[0].headers.cells) == 4


# ---------------------------------------------------------------------------
# 3. Multi-Format Exporters
# ---------------------------------------------------------------------------

class TestExporters:
    @pytest.fixture
    def parsed_doc(self) -> DocumentAST:
        return DocumentParser().parse(SAMPLE_MARKDOWN, title="Test Spec")

    def test_markdown_exporter(self, parsed_doc: DocumentAST):
        exporter = MarkdownExporter()
        out = exporter.export(parsed_doc)
        assert "# Autonomous Architecture Dossier" in out
        assert "| Latency |" in out
        assert "> [!NOTE]" in out
        assert "```python" in out

    def test_html_exporter(self, parsed_doc: DocumentAST):
        exporter = HtmlExporter()
        out = exporter.export(parsed_doc)
        assert "<!DOCTYPE html>" in out
        assert "<title>Test Spec</title>" in out
        assert "<table>" in out
        assert "class=\"callout callout-note\"" in out
        assert "<code" in out

    def test_docx_exporter(self, parsed_doc: DocumentAST):
        exporter = DocxExporter()
        docx_bytes = exporter.export(parsed_doc)

        assert isinstance(docx_bytes, bytes)
        assert len(docx_bytes) > 500

        # Verify it's a valid ZIP with OpenXML parts
        buf = io.BytesIO(docx_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            namelist = zf.namelist()
            assert "[Content_Types].xml" in namelist
            assert "_rels/.rels" in namelist
            assert "word/document.xml" in namelist
            assert "word/styles.xml" in namelist

            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "Autonomous Architecture Dossier" in doc_xml
            assert "System Invariant" in doc_xml
            assert "w:tbl" in doc_xml

    def test_pptx_exporter(self, parsed_doc: DocumentAST):
        exporter = PptxExporter()
        pptx_bytes = exporter.export(parsed_doc)

        assert isinstance(pptx_bytes, bytes)
        assert len(pptx_bytes) > 500

        # Verify valid PPTX ZIP package
        buf = io.BytesIO(pptx_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            namelist = zf.namelist()
            assert "[Content_Types].xml" in namelist
            assert "ppt/presentation.xml" in namelist
            assert "ppt/slides/slide1.xml" in namelist
            assert "ppt/slideMasters/slideMaster1.xml" in namelist

            pres_xml = zf.read("ppt/presentation.xml").decode("utf-8")
            assert "p:presentation" in pres_xml

    def test_xlsx_exporter(self, parsed_doc: DocumentAST):
        exporter = XlsxExporter()
        xlsx_bytes = exporter.export(parsed_doc)

        assert isinstance(xlsx_bytes, bytes)
        assert len(xlsx_bytes) > 500

        # Verify valid XLSX ZIP package
        buf = io.BytesIO(xlsx_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            namelist = zf.namelist()
            assert "[Content_Types].xml" in namelist
            assert "xl/workbook.xml" in namelist
            assert "xl/worksheets/sheet1.xml" in namelist
            assert "xl/sharedStrings.xml" in namelist

            wb_xml = zf.read("xl/workbook.xml").decode("utf-8")
            assert "workbook" in wb_xml

    def test_pdf_exporter(self, parsed_doc: DocumentAST):
        exporter = PdfExporter()
        pdf_bytes = exporter.export(parsed_doc)

        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 1000


# ---------------------------------------------------------------------------
# 4. Archive Packager & Security
# ---------------------------------------------------------------------------

class TestArchivePackager:
    def test_package_and_inspect_artifacts(self):
        packager = ArchivePackager()
        art1 = ArtifactRecord(
            user_id="u1",
            title="Doc 1",
            filename="doc1.md",
            content="# First Document",
            format=ArtifactFormat.MD,
        )
        art2 = ArtifactRecord(
            user_id="u1",
            title="Data 2",
            filename="data.json",
            content='{"key": "value"}',
            format=ArtifactFormat.JSON,
        )
        art1.compute_hash_and_size()
        art2.compute_hash_and_size()

        zip_bytes = packager.package_artifacts([art1, art2], bundle_title="Release Bundle")

        # Inspect archive
        inspection = packager.inspect_archive(zip_bytes)
        assert inspection["file_count"] == 3  # doc1.md, data.json, manifest.json
        assert inspection["has_manifest"] is True
        assert inspection["manifest"]["title"] == "Release Bundle"
        assert len(inspection["manifest"]["entries"]) == 2

    def test_safe_extract_prevents_zip_slip(self, tmp_path: Path):
        packager = ArchivePackager()

        # Construct a malicious ZIP with path traversal
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../evil.txt", "malicious payload")

        malicious_bytes = buf.getvalue()
        target_dir = tmp_path / "safe_output"

        with pytest.raises(ArchiveSecurityError, match="Zip slip"):
            packager.safe_extract(malicious_bytes, target_dir)


# ---------------------------------------------------------------------------
# 5. Render & Inspect Telemetry & Document Linting
# ---------------------------------------------------------------------------

class TestArtifactInspector:
    def test_inspect_document_metrics(self):
        inspector = ArtifactInspector()
        doc = DocumentParser().parse(SAMPLE_MARKDOWN, title="Production Spec")

        report = inspector.inspect_document(doc)
        assert report.word_count > 30
        assert report.reading_time_minutes >= 0.1
        assert report.estimated_tokens > 40
        assert len(report.table_of_contents) >= 3
        assert report.table_count == 1
        assert report.code_block_count == 1
        assert report.callout_count == 2
        assert report.quality_score >= 0.8
        assert report.passed is True

    def test_inspector_detects_empty_tables(self):
        inspector = ArtifactInspector()
        # Bad document with empty table and no title
        bad_md = "| Col1 | Col2 |\n| --- | --- |\n"
        doc = DocumentParser().parse(bad_md, title="Untitled Document")

        report = inspector.inspect_document(doc)
        issues = report.issues
        assert any(i.code == "GENERIC_TITLE" for i in issues)
        assert any(i.code == "EMPTY_TABLE" for i in issues)
        assert report.passed is False  # EMPTY_TABLE is an ERROR


# ---------------------------------------------------------------------------
# 6. ArtifactService Orchestration
# ---------------------------------------------------------------------------

class TestArtifactService:
    def test_create_and_export_lifecycle(self):
        service = ArtifactService()

        # 1. Create document
        record, doc_ast = service.create_document(
            user_id="user_test",
            title="System Benchmark",
            content=SAMPLE_MARKDOWN,
            tags=["infra", "benchmark"],
        )
        assert record.id.startswith("art_")
        assert record.size_bytes > 0
        assert service.get_artifact(record.id) is not None

        # 2. Multi-format exports
        html_out = service.export_artifact(record.id, ArtifactFormat.HTML)
        assert "<!DOCTYPE html>" in html_out

        docx_out = service.export_artifact(record.id, ArtifactFormat.DOCX)
        assert isinstance(docx_out, bytes) and len(docx_out) > 500

        pptx_out = service.export_artifact(record.id, ArtifactFormat.PPTX)
        assert isinstance(pptx_out, bytes) and len(pptx_out) > 500

        xlsx_out = service.export_artifact(record.id, ArtifactFormat.XLSX)
        assert isinstance(xlsx_out, bytes) and len(xlsx_out) > 500

        pdf_out = service.export_artifact(record.id, ArtifactFormat.PDF)
        assert isinstance(pdf_out, bytes) and pdf_out.startswith(b"%PDF")

        # 3. Inspect artifact
        inspection = service.inspect_artifact(record.id)
        assert inspection["artifact_id"] == record.id
        assert "document_analysis" in inspection
        assert inspection["document_analysis"]["passed"] is True

        # 4. Package artifact
        bundle = service.package_artifacts([record.id], bundle_title="Benchmark Bundle")
        assert len(bundle) > 500
        assert bundle.startswith(b"PK")  # ZIP signature

    def test_presentation_and_spreadsheet_creation(self):
        service = ArtifactService()

        # Presentation
        slides = [
            {"title": "Slide 1", "subtitle": "Intro", "bullets": ["Point A", "Point B"]},
            {"title": "Slide 2", "bullets": ["Architecture", "Throughput"]},
        ]
        deck, _ = service.create_presentation("user_test", "Tech Deck", slides)
        assert deck.format == ArtifactFormat.PPTX
        assert isinstance(deck.content, bytes)

        # Spreadsheet
        sheets = [
            {
                "name": "Financials",
                "headers": ["Quarter", "Revenue", "Cost", "Margin"],
                "rows": [["Q1", 1000, 400, 600], ["Q2", 1500, 500, 1000]],
            }
        ]
        sheet, _ = service.create_spreadsheet("user_test", "Q1 Q2 Metrics", sheets)
        assert sheet.format == ArtifactFormat.XLSX
        assert isinstance(sheet.content, bytes)


# ---------------------------------------------------------------------------
# 7. FastAPI REST Surface
# ---------------------------------------------------------------------------

class TestArtifactEndpoints:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from hinaa_api.main import create_app
        app = create_app()
        return TestClient(app)

    def test_document_artifact_endpoint_lifecycle(self, client):
        # 1. Create document
        resp = client.post(
            "/v1/artifacts/documents",
            json={
                "title": "API Strategy Guide",
                "content": "# API Strategy Guide\n\nHigh-performance APIs.\n\n| Endpoint | Status |\n|---|---|\n| /v1/health | 200 |\n",
                "format": "md",
                "tags": ["strategy", "api"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        art_id = data["artifact"]["id"]
        assert art_id.startswith("art_")
        assert data["inspection"]["wordCount"] > 0
        assert data["inspection"]["qualityScore"] > 0.5

        # 2. Get artifact
        get_resp = client.get(f"/v1/artifacts/{art_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["artifact"]["id"] == art_id

        # 3. Inspect artifact
        inspect_resp = client.get(f"/v1/artifacts/{art_id}/inspect")
        assert inspect_resp.status_code == 200
        assert "document_analysis" in inspect_resp.json()["report"]

        # 4. Export to HTML
        export_resp = client.get(f"/v1/artifacts/{art_id}/export?format=html")
        assert export_resp.status_code == 200
        assert "<!DOCTYPE html>" in export_resp.text

        # 5. Export to DOCX
        docx_resp = client.get(f"/v1/artifacts/{art_id}/export?format=docx")
        assert docx_resp.status_code == 200
        assert len(docx_resp.content) > 500

        # 6. Export to PPTX
        pptx_resp = client.get(f"/v1/artifacts/{art_id}/export?format=pptx")
        assert pptx_resp.status_code == 200
        assert len(pptx_resp.content) > 500

        # 7. Export to XLSX
        xlsx_resp = client.get(f"/v1/artifacts/{art_id}/export?format=xlsx")
        assert xlsx_resp.status_code == 200
        assert len(xlsx_resp.content) > 500

        # 8. Package artifact
        pkg_resp = client.post(
            "/v1/artifacts/package",
            json={
                "artifactIds": [art_id],
                "bundleTitle": "Release Package",
                "description": "Production release bundle",
            },
        )
        assert pkg_resp.status_code == 200
        assert pkg_resp.content.startswith(b"PK")
