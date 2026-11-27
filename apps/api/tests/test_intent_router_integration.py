from __future__ import annotations

from hinaa_intent_gate import Intent, classify_with_router


def test_classify_with_router_preserves_gate_and_routes_engineering_turns() -> None:
    decision_chat, route_chat = classify_with_router("Explain why the sky is blue")
    assert decision_chat.intent == Intent.CHAT
    assert route_chat.route == "chat"

    decision_code, route_code = classify_with_router("Refactor the React ChatPanel component and run unit tests")
    assert decision_code.intent == Intent.CHAT
    assert route_code.route == "coding"
    assert route_code.requires_planning is True

    decision_doc, route_doc = classify_with_router("Create a PDF executive summary report")
    assert decision_doc.intent == Intent.DOCUMENT_CREATE
    assert route_doc.route == "documents"
