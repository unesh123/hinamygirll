"""P0.12 directive fixtures §31–§33: split-escape, quote-split, Unicode.

The client must see every decoded character EXACTLY ONCE, no matter where
provider chunks split the raw JSON.
"""

from __future__ import annotations

import pytest

from hinaa_api.providers.display_stream_decoder import (
    AdaptiveStreamDecoder,
    DisplayTextChain,
    DisplayTextStreamDecoder,
    JsonDisplayTextLocator,
    decode_all_display_fields,
    decode_display_field,
)


def _stream_decode(raw_value: str, chunk_size: int = 3) -> str:
    """Feed raw value chars in small chunks like a real provider stream."""
    decoder = DisplayTextStreamDecoder()
    out = []
    for i in range(0, len(raw_value), chunk_size):
        out.append(decoder.feed(raw_value[i : i + chunk_size]))
    out.append(decoder.finish())
    return "".join(out)


def _assert_is_true() -> None:  # pragma: no cover — helper kept for clarity
    assert True


class TestExactlyOnceEmission:
    def test_split_newline_escape_never_duplicates(self) -> None:
        # Directive §31 fixture shape: \\n split across chunks.
        assert _stream_decode('Hello\\' + 'nworld') == "Hello\nworld"
    def test_split_quote_escape_never_duplicates(self) -> None:
        # Directive §32: \" split across arbitrary chunks.
        for split in range(1, len('say \\"hi\\" now')):
            raw = 'say \\"hi\\" now'
            assert _stream_decode(raw, chunk_size=split) == 'say "hi" now', split

    def test_every_split_point_produces_identical_output(self) -> None:
        raw = 'The system uses PostgreSQL\\' + 'nfor durable storage. Line two \\"quoted\\" done.'
        expected = "The system uses PostgreSQL\nfor durable storage. Line two \"quoted\" done."
        for size in range(1, len(raw) + 1):
            assert _stream_decode(raw, chunk_size=size) == expected

    def test_unicode_escape_split_across_chunks(self) -> None:
        for split in (1, 2, 3, 5):
            assert _stream_decode("caf\\u00e9", chunk_size=split) == "café", split

    def test_surrogate_pair_split_across_chunks(self) -> None:
        raw = "\\ud83d\\ude00"  # 😀
        for split in (2, 4, 6, 8, 12):
            assert _stream_decode(raw, chunk_size=split) == "😀", split

    def test_surrogate_pair_split_at_boundary_holds_high_half(self) -> None:
        # High surrogate fully decoded, low surrogate arrives next chunk.
        decoder = DisplayTextStreamDecoder()
        first = decoder.feed("\\ud83d")
        assert first == ""
        second = decoder.feed("\\ude00")
        assert second == "😀"

    def test_replay_after_close_emits_nothing(self) -> None:
        decoder = DisplayTextStreamDecoder()
        assert decoder.feed('hello"') == "hello"
        assert decoder.closed
        assert decoder.feed("world") == ""  # replay must not re-emit
        assert decoder.feed('"') == ""
        assert decoder.emitted_length == 5

    def test_repeated_feed_of_same_chunk_is_idempotent(self) -> None:
        decoder = DisplayTextStreamDecoder()
        assert decoder.feed("abc") == "abc"
        assert decoder.feed("def") == "def"
        # Simulate a parser "recovery" that re-parses from scratch:
        fresh = DisplayTextStreamDecoder()
        assert fresh.feed('hi"') == "hi"


class TestClosingQuoteAndMetadata:
    def test_closing_quote_stops_consumption(self) -> None:
        raw = 'text here","spokenText":"voice line","language":"en-US"}'
        decoder = DisplayTextStreamDecoder()
        emitted = decoder.feed(raw) + decoder.finish()
        assert emitted == "text here"

    def test_escaped_quote_does_not_close_string(self) -> None:
        raw = 'she said \\"hi\\" , fine","spokenText":"x"}'
        decoder = DisplayTextStreamDecoder()
        assert decoder.feed(raw) == 'she said "hi" , fine'

    def test_nested_display_key_shape_is_ignored(self) -> None:
        # Inner quotes MUST be escaped in valid JSON — exactly what providers
        # emit. The decoder keeps escaped quotes in-string and stops only at
        # the real unescaped closing quote.
        raw = 'value with {\\"displayText\\":\\"not really\\"} inside'
        decoder = DisplayTextStreamDecoder()
        out = decoder.feed(raw) + decoder.finish()
        assert 'not really' in out  # stays inside the outer string

    def test_unescaped_inner_quote_closes_string_like_json(self) -> None:
        # Invalid JSON (unescaped inner quote): JSON contract says the string
        # ends there. Decoder honors the contract instead of over-capturing.
        decoder = DisplayTextStreamDecoder()
        out = decoder.feed('value with {"displayText":') + decoder.finish()
        assert out == 'value with {'


class TestLocator:
    def test_finds_value_start_across_split_key(self) -> None:
        full = '{"displayText":"Hello world","spokenText":"Hi"}'
        # Try every split point of the key region.
        for split in range(1, len('"displayText": "')):
            locator = JsonDisplayTextLocator()
            offset = locator.feed(full[:split])
            offset2 = locator.feed(full[split:])
            assert locator.found
            assert (offset if offset >= 0 else offset2) == len('{"displayText":"')

    def test_locator_short_circuits_after_found(self) -> None:
        locator = JsonDisplayTextLocator()
        assert locator.feed('{"displayText":"abc"}') == len('{"displayText":"')
        assert locator.feed('garbage') == locator.value_start

    def test_offset_in_chunk(self) -> None:
        locator = JsonDisplayTextLocator()
        assert locator.feed('{"displayText":') == -1  # key not yet complete
        chunk = ' "Hello"}'
        assert locator.feed(chunk) == len('{"displayText": "')
        idx = locator.offset_in_chunk(chunk)
        assert idx == len(' "')
        assert chunk[idx:].startswith('Hello')


class TestOneShotHelpers:
    def test_decode_display_field_matches_streaming(self) -> None:
        raw = 'Line one\\nLine \\"two\\"\\twith \\u00e9 and \\ud83d\\ude00'
        expected = 'Line one\nLine "two"\twith é and 😀'
        one_shot = decode_display_field(f'{{"displayText":"{raw}"}}')
        streamed = _stream_decode(raw, chunk_size=5)
        assert one_shot == streamed == expected

    def test_decode_all_fields_recovers_continuation_restart(self) -> None:
        # Continuation restarted a fresh JSON object instead of continuing
        # mid-string: both display values are recovered independently.
        doc = (
            '{"displayText":"first segment",'
            '"displayText":"second segment continues"}'
        )
        values = decode_all_display_fields(doc)
        assert values == ["first segment", "second segment continues"]

    def test_invalid_unicode_escape_is_lenient(self) -> None:
        # Lenient contract: unknown/bad escape keeps the escaped char and
        # drops the backslash.
        assert _stream_decode("bad \\uZZZZ escape") == "bad uZZZZ escape"

    def test_partial_escape_at_end_flushed_leniently(self) -> None:
        # finish() flushes a trailing partial escape as literal chars.
        d2 = DisplayTextStreamDecoder()
        assert d2.feed("trailing back\\") == "trailing back"
        assert d2.finish() == "\\"

    def test_empty_and_noop_feeds(self) -> None:
        decoder = DisplayTextStreamDecoder()
        assert decoder.feed("") == ""
        assert decoder.feed('done"') == "done"
        assert decoder.feed("") == ""


class TestDisplayTextChain:
    def test_single_object_streams_exactly_once(self) -> None:
        chain = DisplayTextChain()
        full = '{"displayText":"Hello split world.","spokenText":"Hi"}'
        out = ""
        for i in range(0, len(full), 4):
            out += chain.feed(full[i : i + 4])
        out += chain.finish()
        assert out == "Hello split world."
        assert chain.restarts == 0

    def test_continuation_restart_new_object(self) -> None:
        chain = DisplayTextChain()
        out = chain.feed('{"displayText":"part one",')
        out += chain.feed('"spokenText":"x"}')
        out += chain.feed('{"displayText":"part two",')
        out += chain.feed('"spokenText":"y"}')
        out += chain.finish()
        assert out == "part onepart two"
        assert chain.restarts == 1

    def test_continuation_restart_split_key(self) -> None:
        chain = DisplayTextChain()
        out = chain.feed('{"displayText":"first value","language":"mixed"}')
        # Split the next key across two feeds (real continuation shape: the
        # restart begins with '{', the key splits inside it).
        out += chain.feed('{"display')
        out += chain.feed('Text":"second segment"}')
        out += chain.finish()
        assert out == "first valuesecond segment"
        assert chain.restarts == 1

    def test_post_value_metadata_never_leaks_into_stream(self) -> None:
        # After the first value closes, everything without a restart anchor
        # is post-value metadata and MUST be dropped (not guessed as prose).
        chain = DisplayTextChain()
        out = chain.feed('{"displayText":"body",')
        out += chain.feed('"emotion":{"primary":"happy"},')
        out += chain.feed('"performance":{"facePreset":"soft_smile"}}')
        out += chain.finish()
        assert out == "body"
        assert chain.restarts == 0

    def test_metadata_split_across_chunks_does_not_leak(self) -> None:
        # Feed the whole document one character at a time: no metadata
        # fragment may ever appear in the display stream at any chunking.
        full = '{"displayText":"body text","emotion":{"primary":"happy"},"spokenText":"hi"}'
        for size in (1, 2, 3, 5, 7, 11):
            chain = DisplayTextChain()
            out = ""
            for i in range(0, len(full), size):
                out += chain.feed(full[i : i + size])
            out += chain.finish()
            assert out == "body text", size

    def test_oversized_unanchored_tail_is_dropped(self) -> None:
        chain = DisplayTextChain()
        out = chain.feed('{"displayText":"kept"}')
        out += chain.feed("x" * (DisplayTextChain.RESTART_SCAN_BUFFER_LIMIT + 16))
        out += chain.finish()
        assert out == "kept"

    def test_key_split_across_locator_feeds(self) -> None:
        chain = DisplayTextChain()
        out = chain.feed('{"display')
        out += chain.feed('Text":"late found value"}')
        out += chain.finish()
        assert out == "late found value"

    def test_restart_value_with_split_escapes_stitch_exactly_once(self) -> None:
        # Full integration: first object cut mid-escape at restart boundary,
        # second object carrying the rest — every char exactly once.
        chain = DisplayTextChain()
        full = (
            '{"displayText":"Part A line one\\nline two.","spokenText":"x"}'
            '{"displayText":"Part B continues \\"quoted\\" here.","spokenText":"y"}'
        )
        out = ""
        for i in range(0, len(full), 5):
            out += chain.feed(full[i : i + 5])
        out += chain.finish()
        assert out == 'Part A line one\nline two.Part B continues "quoted" here.'
        assert chain.restarts == 1
        assert out.count("Part A") == 1
        assert out.count("Part B") == 1

class TestSection31RegressionFixture:
    """The exact production regression: duplicated line from partial-JSON re-parse."""

    def test_chunk_a_then_chunk_b_emits_once(self) -> None:
        chunk_a = '{"displayText":"The system uses PostgreSQL\\'
        chunk_b = 'nfor durable storage."}'

        locator = JsonDisplayTextLocator()
        va_start = locator.feed(chunk_a)
        decoder = DisplayTextStreamDecoder()

        out = ""
        if va_start >= 0:
            # Value begins inside chunk A: feed only the raw chars after the
            # opening quote. The locator's absolute offset applies to the
            # concatenated stream, so slice chunk A directly.
            out += decoder.feed(chunk_a[va_start:])
        out += decoder.feed(chunk_b)
        out += decoder.finish()

        assert out == "The system uses PostgreSQL\nfor durable storage."
        assert out.count("The system uses PostgreSQL") == 1

    def test_chain_reproduces_directive_31_fixture(self) -> None:
        # Same fixture through the full-chain entry point used by agent-router.
        chunk_a = '{"displayText":"The system uses PostgreSQL\\'
        chunk_b = 'nfor durable storage."}'
        chain = DisplayTextChain()
        out = chain.feed(chunk_a) + chain.feed(chunk_b) + chain.finish()
        assert out == "The system uses PostgreSQL\nfor durable storage."
        assert out.count("The system uses PostgreSQL") == 1


class TestAdaptiveStreamDecoderEdgeCases:
    """Directive §7: escaped newline, quote, backslash, unicode, 1-char chunks, randomized boundaries."""

    def test_single_character_chunks_json(self) -> None:
        raw_json = '{"displayText":"Line 1\\nLine 2 with \\"quotes\\" and \\u2764."}'
        decoder = AdaptiveStreamDecoder()
        emitted = []
        for ch in raw_json:
            delta = decoder.feed(ch)
            if delta:
                emitted.append(delta)
        rest = decoder.finish()
        if rest:
            emitted.append(rest)
        result = "".join(emitted)
        assert result == 'Line 1\nLine 2 with "quotes" and ❤.'

    def test_single_character_chunks_plain_prose(self) -> None:
        prose = "This is a direct markdown stream with **bold** text and newlines.\n\nSecond paragraph."
        decoder = AdaptiveStreamDecoder()
        emitted = []
        for ch in prose:
            delta = decoder.feed(ch)
            if delta:
                emitted.append(delta)
        rest = decoder.finish()
        if rest:
            emitted.append(rest)
        result = "".join(emitted)
        assert result == prose

    def test_randomized_chunk_splits(self) -> None:
        import random
        random.seed(42)
        raw_json = '{"displayText":"A complex document with\\nmultiple\\nescapes \\"and\\" symbols \\u2728."}'
        expected = 'A complex document with\nmultiple\nescapes "and" symbols ✨.'
        for _ in range(10):
            decoder = AdaptiveStreamDecoder()
            emitted = []
            idx = 0
            while idx < len(raw_json):
                step = random.randint(1, 7)
                chunk = raw_json[idx : idx + step]
                delta = decoder.feed(chunk)
                if delta:
                    emitted.append(delta)
                idx += step
            rest = decoder.finish()
            if rest:
                emitted.append(rest)
            assert "".join(emitted) == expected

    def test_backslash_boundary_without_escape(self) -> None:
        raw = "Folder path: C:\\Users\\unesh\\Desktop\\file.txt"
        decoder = AdaptiveStreamDecoder()
        emitted = []
        for i in range(0, len(raw), 4):
            delta = decoder.feed(raw[i : i + 4])
            if delta:
                emitted.append(delta)
        rest = decoder.finish()
        if rest:
            emitted.append(rest)
        assert "".join(emitted) == raw


# Measured from a live agent-router turn on 2026-09-22: the flash-tier brain
# wrote its own call into the answer between two spoken sentences. It closes
# <tool_call> with </toolCall>, so nothing here matches by tag identity.
_INVENTED_CALL_REPLY = (
    "\n\nHere are some Tokyo Ghoul pics for you, babe! Let me search them up. \U0001f5a4\n\n"
    "<tool_call>\ntoolName: image_search\n</toolCall>\n\n"
    "<toolCall>toolName: image_search\n"
    '<toolArg name=query>Tokyo Ghoul</toolArg>\n</toolCall>\n\n'
    "I searched for Tokyo Ghoul images, babe!"
)


def _stream_prose(raw: str, chunk_size: int) -> str:
    decoder = AdaptiveStreamDecoder()
    emitted = []
    for i in range(0, len(raw), chunk_size):
        emitted.append(decoder.feed(raw[i : i + chunk_size]))
    emitted.append(decoder.finish())
    return "".join(emitted)


@pytest.mark.parametrize("chunk_size", [1, 2, 3, 5, 7, 11, 13, 4000])
def test_invented_tool_call_never_reaches_the_reader(chunk_size: int) -> None:
    """These deltas are what the screen appends and the voice queue speaks, so
    holding a tag back is the only thing that keeps XML out of her mouth."""
    out = _stream_prose(_INVENTED_CALL_REPLY, chunk_size)
    assert "<" not in out
    for noise in ("toolName", "toolArg", "image_search"):
        assert noise not in out
    assert "Here are some Tokyo Ghoul pics for you, babe!" in out
    assert "I searched for Tokyo Ghoul images, babe!" in out


def test_angle_brackets_that_are_not_a_tool_call_survive() -> None:
    raw = "Wrap the label in <b class='x'> and </b> tags, then call render()."
    assert _stream_prose(raw, 3) == raw


def test_a_tool_tag_split_across_deltas_is_still_dropped() -> None:
    decoder = AdaptiveStreamDecoder()
    out = ""
    for piece in (
        "Sure! <",
        "tool_cal",
        "l>",
        "toolName: web_search",
        "</toolCall>",
        " Done.",
    ):
        out += decoder.feed(piece)
    out += decoder.finish()
    assert out == "Sure!  Done."


def _closing(name: str) -> str:
    return "<" + "/" + name + ">"


def test_the_invoke_dialect_of_invented_call_markup_is_dropped_too() -> None:
    """Measured the next live turn: the model changed dialect and wrote an
    invoke element with parameter children instead of a tool_call block."""
    raw = (
        "Let me grab some Tokyo Ghoul pics for you babe!\n\n"
        + '<invoke name="freepik_image_generate">\n'
        + '<parameter name="prompt">Tokyo Ghoul anime artwork' + _closing("parameter") + "\n"
        + '<parameter name="count">8' + _closing("parameter") + "\n"
        + _closing("invoke") + "\n\n"
        + "One sec~"
    )
    out = _stream_prose(raw, 5)
    assert out.startswith("Let me grab some Tokyo Ghoul pics for you babe!")
    assert out.endswith("One sec~")
    for noise in ("invoke", "parameter", "freepik_image_generate", "8"):
        assert noise not in out


def test_a_third_spelling_of_the_same_invented_call_is_dropped() -> None:
    """Measured live one turn later: tool_argument and tool_arguments elements,
    spellings no name list contained. The structural rule catches them anyway."""
    raw = (
        "I'll search for Tokyo Ghoul images for you, babe!\n\n"
        + '<tool_argument name="count">8' + _closing("tool_argument") + "\n"
        + '<tool_arguments>{"query": "Tokyo Ghoul official art", "count": 8}'
        + _closing("tool_arguments") + "\n\n"
        + "Give me one sec~"
    )
    out = _stream_prose(raw, 6)
    assert out.startswith("I'll search for Tokyo Ghoul images for you, babe!")
    assert out.endswith("Give me one sec~")
    for noise in ("tool_argument", "tool_arguments", "count", "8"):
        assert noise not in out
