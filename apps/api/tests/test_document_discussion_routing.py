"""Capability discussion must not authorize artifact creation."""
import pytest

from hinaa_api.tools.intent_gate import sanction_tools


@pytest.mark.parametrize("text", [
    "How can I improve PDF generation?",
    "Explain how to generate a PDF document",
    "Can you explain how to create a PDF?",
    "What is the best way to generate documents?",
    "If I ask you to create a PDF, what happens?",
    "Do not generate a PDF",
])
def test_discussion_does_not_sanction_documents(text):
    assert not sanction_tools(text).allowed


@pytest.mark.parametrize("text", [
    "Create a detailed colorful report as PDF",
    "Generate a PDF about photosynthesis",
    "Can you create a PDF about my study plan?",
])
def test_concrete_document_requests_remain_supported(text):
    assert "pdf_generate" in sanction_tools(text).allowed
