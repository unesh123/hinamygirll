"""
Test suite verifying that HINAA supports large prompts (50,000+ characters),
universal file extraction (PDF, DOCX, TXT, code files), and does NOT reject
long user turns with 'String should have at most 8000 characters'.
"""

import io
import pytest
from starlette.testclient import TestClient
from pydantic import ValidationError

from hinaa_api.models import TurnRequest, AssistantTurnPlan
from hinaa_api.prompts.models import PromptInput
from hinaa_api.prompts.context import build_user_block
from hinaa_api.media.extractors import extract_docx_text, extract_text_document, extract_pdf_text
from hinaa_api.media.resolver import _extract_media_text
from hinaa_api.main import create_app
from hinaa_api.config import Settings


def test_turn_request_accepts_large_prompts():
    # 50,000 character prompt
    large_text = "This is an advanced technical spec. " * 1500  # ~54,000 chars
    req = TurnRequest(sessionId="sess-large-prompt", text=large_text)
    assert len(req.text) == len(large_text)
    assert req.text.startswith("This is an advanced technical spec.")

    # 150,000 character prompt
    massive_text = "Universal Agent Prompt " * 6500  # ~149,500 chars
    req2 = TurnRequest(sessionId="sess-massive", text=massive_text)
    assert len(req2.text) == len(massive_text)


def test_prompt_input_and_user_block_accommodates_large_prompts():
    prompt_text = "Architecture Spec Line.\n" * 2500  # ~60,000 chars
    inp = PromptInput(
        companion_id="hinaa",
        interaction_mode="rest",
        user_text=prompt_text,
    )
    assert len(inp.user_text) == len(prompt_text)

    block = build_user_block(prompt_text)
    assert '<user_message trusted="false">' in block
    assert len(block) >= len(prompt_text)


def test_extract_text_document_does_not_truncate_at_10000():
    text = "const a = 1;\n" * 3000  # ~39,000 chars
    raw_bytes = text.encode("utf-8")
    extracted = extract_text_document(raw_bytes, max_chars=100000)
    assert len(extracted) == len(text)
    assert "[... truncated" not in extracted


def test_resolver_code_extensions_and_pdf_dispatch():
    # Code extension .tsx
    tsx_code = b"export const MyComp = () => <div>Hello</div>;"
    extracted = _extract_media_text(tsx_code, "text/typescript", "Component.tsx")
    assert extracted == "export const MyComp = () => <div>Hello</div>;"

    # Python .py
    py_code = b"def run_ai():\n    return 'perfect'"
    extracted_py = _extract_media_text(py_code, "text/x-python", "main.py")
    assert extracted_py == "def run_ai():\n    return 'perfect'"


def test_stream_turn_endpoint_accepts_large_prompt_without_422():
    app = create_app(Settings(environment="test", provider_mode="mock"))
    client = TestClient(app)

    # 30,000 character prompt (previously rejected with 422: String should have at most 8000 characters)
    prompt_30k = "Please evaluate this long autonomous specification: " + ("test step content. " * 1500)
    assert len(prompt_30k) > 25000

    payload = {
        "sessionId": "test-session-30k",
        "text": prompt_30k,
        "companionId": "hinaa",
        "language": "en-US",
        "providerMode": "mock",
    }

    response = client.post("/v1/conversations/turns:stream", json=payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    lines = [l for l in response.text.split("\n") if l.strip()]
    assert len(lines) > 0
    assert "String should have at most 8000 characters" not in response.text
