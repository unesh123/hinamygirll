from io import BytesIO
import importlib.util
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas
from hinaa_api.document_ingestion import extract_uploaded_document, MAX_UPLOAD_BYTES


def test_extract_route_accepts_text_and_sanitizes_client_path(client):
    response = client.post("/v1/documents/extract", files={"file": ("../../notes.txt", b"Real document text", "text/plain")})
    assert response.status_code == 200
    assert response.json()["text"] == "Real document text"


def test_pdf_upload_extracts_real_page_text():
    content = BytesIO()
    pdf = canvas.Canvas(content)
    pdf.drawString(40, 700, "Hina document extraction verified")
    pdf.save()
    result = extract_uploaded_document(content.getvalue(), "report.pdf")
    assert "Hina document extraction verified" in result.text
    assert result.kind == "pdf"


@pytest.mark.parametrize("name,content,status", [("empty.txt", b"", 400), ("picture.png", b"not text", 400), ("broken.pdf", b"broken binary", 400), ("large.txt", b"x" * (MAX_UPLOAD_BYTES + 1), 413)], ids=["empty", "unsupported", "invalid-pdf", "too-large"])
def test_invalid_uploads_are_explicit_errors(client, name, content, status):
    response = client.post("/v1/documents/extract", files={"file": (name, content, "application/octet-stream")})
    assert response.status_code == status
    assert "success" not in response.json()


def _container_module():
    path = Path(__file__).resolve().parents[3] / "scripts/start-api-container.py"
    spec = importlib.util.spec_from_file_location("container_start", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cloud_configuration_fails_closed_without_owner_or_production_auth():
    errors = _container_module().validate_environment({})
    assert any("owner" in error for error in errors)
    assert any("production Clerk" in error for error in errors)


def test_cloud_configuration_accepts_explicit_owner_and_production_auth():
    env = {"ENVIRONMENT": "production", "HINAA_AUTH_MODE": "clerk", "CLERK_SECRET_KEY": "sk_live_test_fixture", "HINAA_ALLOWED_USER_IDS": "user_fixture", "CLERK_AUTHORIZED_PARTIES": "https://hina.example", "HINAA_ALLOWED_ORIGINS": "https://hina.example", "HINAA_PERSISTENCE_ENABLED": "true"}
    validate = _container_module().validate_environment
    assert validate(env) == []
    env["HINAA_ALLOW_REMOTE_LOCAL_TOOLS"] = "true"
    assert any("must remain false" in error for error in validate(env))


@pytest.mark.parametrize("origin", ["http://hina.example", "https://*.example", "https://hina.example/path", "https://hina.example?key=value", "https://user:password@hina.example", "https://hina.example:invalid"])
def test_cloud_origins_reject_wildcards_credentials_and_paths(origin):
    assert not _container_module()._https_origin(origin)
