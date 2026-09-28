"""Her visible reply must never carry the machinery that produced it.

Every case here was read off a production chat bubble, not invented: a weak
brain that cannot use structured tool calling writes the call into its answer,
so he saw literal `<tool_calls>` tags and a fenced ```tool_request``` block on
image turns, and a gateway wrapped the rewritten prompt in `<![CDATA[...]]>`
markup. The CDATA rule is the one that keeps this honest: markup is stripped,
the words inside it are not.
"""

from __future__ import annotations

from hinaa_api.prompts.fallback import normalize_gateway_turn_payload
from hinaa_api.prompts.performance import build_plan_from_text


def _native(raw_text: str) -> str:
    """The reply as the native tool-calling path renders it.

    A different provider pipeline from the one above: the flash-tier brains that
    answered these turns never wrote JSON, so their prose goes through
    `build_plan_from_text` and its own scrubber.
    """
    return build_plan_from_text(
        text=raw_text, companion_id="hinaa", language="en-US", depth="conversational"
    ).displayText


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


def _display_with_job(raw_text: str) -> str:
    """The same reply on a turn that did file a call, which is the only turn where
    a block repeating that call's arguments is machinery."""
    payload = {
        "response": "neutral",
        "spokenText": raw_text,
        "displayText": raw_text,
        "language": "en",
        "emotion": {"type": "neutral", "valence": 0.0, "arousal": 0.0},
        "performance": {},
        "memoryCandidates": [],
        "toolRequests": [
            {"toolName": "image_generate", "parameters": {"prompt": "Mikasa", "count": 1}}
        ],
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


def test_a_tool_tag_with_attributes_is_not_shown_as_prose() -> None:
    """Live bubble from `generate mikasa images`: the same call, spelled with the
    singular tag and its attributes, and no closing tag at all."""
    closed = _display(
        "Let me generate that for you now!\n"
        '<tool name="image_generate" tool_call_id="img_mikasa_002">Mikasa Ackerman '
        'portrait, red scarf</tool>\nIt is on the way!'
    )
    assert "<tool" not in closed
    assert "img_mikasa_002" not in closed
    assert "Mikasa Ackerman portrait" not in closed
    assert "Let me generate that for you now!" in closed
    assert "It is on the way!" in closed

    dangling = _display(
        'Alright! <tool name="image_generate" tool_call_id="img_mikasa_002">'
        "Mikasa Ackerman portrait, close up face shot"
    )
    assert "<tool" not in dangling
    assert "Mikasa Ackerman portrait" not in dangling
    assert dangling == "Alright!"


def test_a_closing_tag_with_no_opening_pair_is_stripped_without_losing_her_words() -> None:
    """Live bubble from `make me a picture of a red fox in the rain`: the call's
    closing tag arrived on its own. The tag is machinery; the sentence in front of
    it is the reply, so only the markup goes."""
    shown = _display(
        "<babe, I'd love to make this for you! A red fox in the rain sounds "
        "absolutely magical. Let me create that for you right now~> </tool>"
    )
    assert "</tool>" not in shown
    assert "A red fox in the rain sounds absolutely magical" in shown
    assert "Let me create that for you right now~" in shown


def test_arguments_echoed_as_a_json_block_do_not_repeat_the_job() -> None:
    """Live bubble from `generate mikasa images` after three other spellings of
    this leak were closed: the call came back fenced as data, on the same turn
    that filed it."""
    shown = _display_with_job(
        "Generating Mikasa Ackerman images for you right now, babe! Let me create "
        "some stunning visuals. ```json\n"
        '{\n  "prompt": "Mikasa Ackerman Attack on Titan, close up portrait, '
        'wearing iconic red scarf, detailed anime art style",\n'
        '  "aspect_ratio": "1:1",\n  "quality": "hd"\n}\n```'
    )
    assert "```" not in shown
    assert "aspect_ratio" not in shown
    assert "close up portrait" not in shown
    assert "Generating Mikasa Ackerman images for you right now" in shown

    # The same leak with no line break, which is how the stream arrived.
    inline = _display_with_job(
        'Generating Mikasa Ackerman images for you right now. ```json { "prompt": '
        '"Mikasa Ackerman close up portrait, red scarf", "aspect_ratio": "1:1", '
        '"quality": "hd" } ```'
    )
    assert "```" not in inline
    assert "aspect_ratio" not in inline
    assert inline == "Generating Mikasa Ackerman images for you right now."


def test_a_json_block_stays_when_the_turn_filed_nothing() -> None:
    """Without a call to echo, that same block is the answer he asked for."""
    text = (
        'Here is the shape your image call takes:\n\n```json\n'
        '{ "prompt": "a red fox", "aspect_ratio": "1:1", "quality": "hd" }\n```'
    )
    assert _display(text) == text


def test_the_code_he_asked_for_survives_a_turn_that_filed_a_job() -> None:
    text = (
        "Here is the function:\n\n```python\ndef greet():\n    return 'hi'\n```\n\n"
        "That returns a greeting."
    )
    assert _display_with_job(text) == text


def test_mangled_argument_tags_take_the_prompt_with_them() -> None:
    """Live bubble from `generate mikasa images`. The close names no opening tag
    and is not even terminated, so nothing can pair it by name."""
    shown = _display(
        "Generating Mikasa Ackerman images for you right now! I'll create a few "
        "variations — let me kick that off. <arg_value>Mikasa Ackerman from Attack "
        "on Titan, detailed anime artwork, red scarf, high quality anime "
        "illustration style, dynamic pose</arg400x600</arg_key>"
    )
    assert "arg_value" not in shown
    assert "arg400x600" not in shown
    assert "arg_key" not in shown
    assert "detailed anime artwork" not in shown
    assert "let me kick that off" in shown


def test_a_trailing_python_style_call_is_not_shown_as_prose() -> None:
    """Live bubble from a gemini flash-lite image turn."""
    shown = _display(
        "Let me conjure up a stunning image of a vivid red fox for you! "
        'ToolRequest: image_generate(prompt="A stunning, highly detailed digital '
        'painting of a vibrant red fox standing in serene rain")'
    )
    assert "image_generate" not in shown
    assert "ToolRequest" not in shown
    assert "Let me conjure up a stunning image" in shown


def test_an_answer_about_the_tool_request_api_keeps_its_words() -> None:
    text = "The tool request API takes a name and parameters, and you confirm it in Settings."
    assert _display(text) == text


def test_cdata_markup_unwraps_without_losing_its_words() -> None:
    shown = _display(
        "Alright babe, let me draw that for you right now!\n\n"
        "<![CDATA[a beautiful red paper origami crane sitting on a clean white table]]>\n"
    )
    assert "CDATA" not in shown
    assert "<![" not in shown and "]]>" not in shown
    assert "a beautiful red paper origami crane sitting on a clean white table" in shown


def test_fenced_tool_call_block_is_not_shown_as_prose() -> None:
    """Live bubble from an image turn: her own invocation arrived as a fence."""
    shown = _display(
        "I'll generate some Mikasa Ackerman images for you right away, babe!\n\n"
        "```tool_request{brain=\"default\", name=\"image_generate\", arguments="
        "{\"prompt\": \"Mikasa Ackerman from Attack on Titan, red scarf\"}}\n```"
    )
    assert "tool_request" not in shown
    assert "image_generate" not in shown
    assert "```" not in shown
    assert "I'll generate some Mikasa Ackerman images for you right away" in shown


def test_a_tool_call_the_stream_never_closed_is_still_not_shown() -> None:
    shown = _display("Sure! Here it comes.\n```tool_call{ name=\"web_search\", ")
    assert "tool_call" not in shown
    assert shown == "Sure! Here it comes."


def test_bracketed_invocation_envelope_is_not_shown_as_prose() -> None:
    """Live bubble from `make me a picture of a red fox in the rain`, written by
    the flash-tier brain that actually answered the turn."""
    shown = _display(
        "## Generating your image... [IMAGE_GENERATE] {\"prompt\": \"A beautiful "
        "red fox standing in the rain, cinematic lighting, 4k quality\"} "
        "[/IMAGE_GENERATE]"
    )
    assert "[IMAGE_GENERATE]" not in shown
    assert "[/IMAGE_GENERATE]" not in shown
    assert "prompt" not in shown
    assert "red fox standing in the rain" not in shown
    assert "Generating your image" in shown


def test_an_invocation_the_brain_never_finished_does_not_leak_its_arguments() -> None:
    shown = _display(
        "On it! [IMAGE_GENERATE] {\"prompt\": \"Mikasa Ackerman with a red scarf"
    )
    assert "[IMAGE_GENERATE]" not in shown
    assert "Mikasa Ackerman with a red scarf" not in shown
    assert shown == "On it!"


def test_brackets_that_are_not_an_invocation_keep_their_words() -> None:
    for text in (
        "Try [START] then [END] in that order, babe.",
        "Set the flag to [NOTE] {see the docs} at the end.",
    ):
        assert _display(text) == text


def test_a_code_block_he_asked_for_survives() -> None:
    text = (
        "Here is the function:\n\n```python\ndef greet():\n    return 'hi'\n```\n\n"
        "That returns a greeting."
    )
    assert _display(text) == text


def test_ordinary_reply_is_left_alone() -> None:
    text = "Hey babe! How's your day going?"
    assert _display(text) == text


def test_a_closing_tag_reaches_him_clean_on_the_native_path() -> None:
    """Same leak, other pipeline. These two bubbles were read off the live thread
    after the JSON-gateway rules were already in place, which proved the rules
    existed in one sanitizer and the turns went through another."""
    shown = _native(
        "A red fox in the rain sounds absolutely magical. "
        "Let me create that for you right now. 🦊🌧️ </tool>"
    )
    assert "</tool>" not in shown
    assert "A red fox in the rain sounds absolutely magical" in shown
    assert "Let me create that for you right now." in shown


def test_a_fenced_invocation_reaches_him_clean_on_the_native_path() -> None:
    """Live bubble from `generate mikasa images`: her own call, fenced as though
    it were an example, under a heading she wrote about it."""
    shown = _native(
        "## Generating Mikasa Images\n\n"
        "I'll create some beautiful artwork of Mikasa for you right now!\n\n"
        "```tool_call:freepik_image_generate```"
    )
    assert "```" not in shown
    assert "freepik_image_generate" not in shown
    assert "tool_call" not in shown
    assert "I'll create some beautiful artwork of Mikasa for you right now!" in shown


def test_the_native_path_still_keeps_the_code_he_asked_for() -> None:
    """The fence rule must not become a blanket: a fenced call is machinery, a
    fenced function is the answer."""
    text = (
        "Here is the function:\n\n```python\ndef greet():\n    return 'hi'\n```\n\n"
        "That returns a greeting."
    )
    assert _native(text) == text
