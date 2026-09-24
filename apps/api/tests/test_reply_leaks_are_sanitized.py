"""Her visible reply must never carry the machinery that produced it.

Both cases below were read off production chat bubbles, not invented: a weak
brain that cannot use structured tool calling writes the call into its answer,
so he saw literal `<tool_calls>` tags on an image turn, and a gateway wrapped
the rewritten prompt in `<![CDATA[...]]>` markup. The CDATA rule is the one that
keeps this honest: markup is stripped, the words inside it are not.
"""

from hinaa_api.prompts.fallback import normalize_gateway_turn_payload


def _display(raw_text: str) -> str:
    payload = {
        "response": "neutral",
        "spokenText": raw_text,
        "displayText": raw_text,
        "language": "en",
        "emotion": {"type": "neutral", "valence": 0.0, "arousal": 0.0},
        "performance": {},
        "memoryCandidates": [],
        "toolRequests": [],
    }
    return normalize_gateway_turn_payload(payload)["displayText"]


def test_leaked_tool_call_envelope_is_not_shown_as_prose() -> None:
    shown = _display(
        "Alright babe, let me create that image for you!\n\n"
        "<tool_calls>\n"
        "A majestic red fox sitting in the rain at night, cinematic lighting\n"
        "</tool_calls>\n\n"
        "The image is generating now — I'll let you know once it's ready!"
    )
    assert "<tool_calls>" not in shown
    assert "</tool_calls>" not in shown
    # The prose he actually asked for survives on both sides of the envelope.
    assert "let me create that image" in shown
    assert "image is generating now" in shown


def test_cdata_markup_unwraps_without_losing_its_words() -> None:
    shown = _display(
        "Alright babe, let me draw that for you right now!\n\n"
        "<![CDATA[a beautiful red paper origami crane sitting on a clean white table]]>\n"
    )
    assert "CDATA" not in shown
    assert "<![" not in shown and "]]>" not in shown
    assert "a beautiful red paper origami crane sitting on a clean white table" in shown


def test_ordinary_reply_is_left_alone() -> None:
    text = "Hey babe! How's your day going?"
    assert _display(text) == text
