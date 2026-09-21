"""Escape-safe incremental decoder for streaming JSON ``displayText`` (P0.12).

Root cause fixed here (directive §4): the old agent-router streamer ran a
regex over the *entire accumulated partial JSON buffer* on every chunk and
re-extracted ``displayText`` with order-dependent ``str.replace`` unescaping.
When an escape sequence such as ``\\n`` or ``\\"`` split across two provider
chunks, the same fragment was emitted twice (or corrupted):

    chunk 1: {"displayText":"Hello\\
    chunk 2: nworld"}
    old behavior: emit "Hello"  →  emit "Hello\\nworld"   (DUPLICATE)

This module replaces that pattern with a true incremental JSON string
decoder (directive §5 option C / §6 exactly-once emission):

- escape sequences are parsed with bounded lookahead, never a whole-buffer
  regex, so ``\\n`` / ``\\"`` / ``\\uXXXX`` (and surrogate pairs) split
  across arbitrary chunk boundaries decode exactly once;
- only NEW decoded characters past ``emitted_length`` are ever returned;
- an unescaped ``"`` terminates consumption, so trailing JSON metadata
  (``spokenText``, ``language``, …) never leaks into the text;
- recovery/re-parse of an already-decoded buffer emits nothing.

Continuation contract (directive §18): when the runtime continues a cut
response, the continuation segment RESTARTS a fresh JSON object, i.e. a
new ``{"displayText": …`` appears in the stream. :class:`DisplayTextChain`
stitches those segments exactly once via a deterministic bounded-buffer
anchor search. Mid-string prose resumes are deliberately NOT guessed at —
ambiguous fragments (metadata split mid-key) cannot be distinguished from
prose, so the scanner drops them instead of corrupting the display stream.
"""

from __future__ import annotations

import re

from .tool_call_narration import SimulatedToolCallFilter, TOOLISH_TAG_SOURCE

__all__ = [
    "DisplayTextStreamDecoder",
    "JsonDisplayTextLocator",
    "DisplayTextChain",
    "AdaptiveStreamDecoder",
    "strip_simulated_tool_calls",
    "decode_display_field",
    "decode_all_display_fields",
    "DISPLAY_KEY_PATTERN",
]

# Matches the displayText key up to and including the opening quote of its
# string value. Used for locating the stream start and for salvage parsing.
DISPLAY_KEY_PATTERN = re.compile(r'"displayText"\s*:\s*"')

# Longest possible prefix of a *split* key match that must be carried across
# chunks: `"displayText": "` is 16 chars; whitespace tolerance adds headroom.
_LOCATOR_CARRY_CHARS = 24

_SIMPLE_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


def _is_complete_u_escape(s: str) -> bool:
    return (
        len(s) >= 6
        and s[0] == "\\"
        and s[1] == "u"
        and all(c in "0123456789abcdefABCDEF" for c in s[2:6])
    )


class DisplayTextStreamDecoder:
    """Incrementally decode one JSON string value, emitting each character once.

    Feed raw JSON source characters (the bytes AFTER the ``displayText``
    opening quote) through :meth:`feed`; every call returns exactly the
    newly decoded characters. Safe against:

    - escape sequences split across feeds (``\\`` at a chunk end waits for
      its continuation instead of guessing);
    - ``\\uXXXX`` escapes split across feeds;
    - UTF-16 surrogate pairs split across feeds (a lone high surrogate is
      held until its low half arrives, or downgraded to U+FFFD);
    - an unescaped ``"`` closing the string (consumption stops; later
      metadata is exposed via :attr:`tail_after_close` instead of leaking).
    """

    def __init__(self) -> None:
        self._pending = ""  # raw chars held back awaiting escape continuation
        self._held_high: int | None = None  # high surrogate awaiting its low half
        self._tail = ""  # unconsumed raw chars from the closing quote onward
        self.emitted_length = 0  # decoded characters returned so far
        self.closed = False  # closing unescaped quote seen

    @property
    def decoded_length(self) -> int:
        return self.emitted_length

    @property
    def tail_after_close(self) -> str:
        """Raw chars from the closing quote onward (valid once closed)."""
        return self._tail

    def take_tail(self) -> str:
        """Return and clear :attr:`tail_after_close` (consume-once)."""
        tail, self._tail = self._tail, ""
        return tail

    def feed(self, raw: str) -> str:
        if self.closed or not raw:
            return ""
        data = self._pending + raw
        self._pending = ""
        out: list[str] = []
        i = 0
        n = len(data)
        while i < n and not self.closed:
            ch = data[i]
            if ch != "\\":
                if ch == '"':
                    self.closed = True
                    self._tail = data[i:]
                    break
                if self._held_high is not None:
                    out.append("\ufffd")
                    self._held_high = None
                out.append(ch)
                i += 1
                continue
            # ---- Escape sequence ----
            if n - i < 2:
                self._pending = data[i:]  # partial: carry for next feed
                break
            esc = data[i + 1]
            if esc != "u":
                if self._held_high is not None:
                    out.append("\ufffd")
                    self._held_high = None
                mapped = _SIMPLE_ESCAPES.get(esc)
                out.append(mapped if mapped is not None else esc)
                i += 2
                continue
            if n - i < 6:
                self._pending = data[i:]  # partial \uXXXX: carry
                break
            try:
                code = int(data[i + 2 : i + 6], 16)
            except ValueError:
                if self._held_high is not None:
                    out.append("\ufffd")
                    self._held_high = None
                out.append(esc)  # lenient: keep the escaped char
                i += 2
                continue
            i += 6
            if 0xD800 <= code <= 0xDBFF:
                if self._held_high is not None:
                    out.append("\ufffd")  # two highs in a row: salvage first
                    self._held_high = None
                lookahead = data[i : i + 6]
                if _is_complete_u_escape(lookahead):
                    try:
                        low = int(lookahead[2:6], 16)
                    except ValueError:  # pragma: no cover — guarded
                        low = -1
                    if 0xDC00 <= low <= 0xDFFF:
                        code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                        i += 6
                        out.append(chr(code))
                    else:
                        out.append("\ufffd")
                else:
                    # High surrogate fully decoded but its pair is absent or
                    # split: hold it, carry the partial remainder.
                    self._held_high = code
                    self._pending = data[i:]
                    break
                continue
            if 0xDC00 <= code <= 0xDFFF:
                if self._held_high is not None:
                    code = 0x10000 + ((self._held_high - 0xD800) << 10) + (code - 0xDC00)
                    self._held_high = None
                else:
                    code = 0xFFFD  # lone low surrogate
                out.append(chr(code))
                continue
            if self._held_high is not None:
                out.append("\ufffd")  # held high not followed by a low
                self._held_high = None
            out.append(chr(code))
        text = "".join(out)
        self.emitted_length += len(text)
        return text

    def finish(self) -> str:
        """Flush residual partial escape / lone surrogate at end-of-stream.

        A trailing lone ``\\`` or partial ``\\u0`` means the model was cut
        mid-escape; emitting the raw chars literally is the least-lossy
        salvage and can never duplicate previously emitted text.
        """
        if self.closed:
            return ""
        out: list[str] = []
        if self._held_high is not None:
            out.append("\ufffd")
            self._held_high = None
        tail, self._pending = self._pending, ""
        if tail:
            try:
                out.append(bytes(tail, "ascii").decode("unicode_escape"))
            except Exception:
                out.append(tail)
        text = "".join(out)
        self.emitted_length += len(text)
        return text


class JsonDisplayTextLocator:
    """Find the absolute stream offset where the displayText VALUE begins.

    The key itself may split across provider chunks, so unmatched tails are
    carried in a bounded window (directive §31 fixture: the split can occur
    anywhere inside `"displayText": "`). Once found, the offset is stable
    and later feeds short-circuit.
    """

    def __init__(self) -> None:
        self._carry = ""
        self._base = 0  # absolute offset of _carry[0] in the raw stream
        self._chunk_start = 0  # absolute offset where the last fed chunk began
        self._last_window = ""  # window searched on the feed that found the key
        self._match_end_in_window = -1
        self.value_start = -1  # absolute offset just AFTER the opening quote

    @property
    def found(self) -> bool:
        return self.value_start >= 0

    @property
    def value_source_text(self) -> str:
        """Raw text from the value start onward, from the stored match window.

        Valid only on the feed that discovered the key; covers the case
        where the key/value boundary completed inside carried history
        (split key), so the value does not begin inside the fed chunk.
        """
        if self._match_end_in_window < 0:
            return ""
        return self._last_window[self._match_end_in_window :]

    def feed(self, chunk: str) -> int:
        """Return the absolute value-start offset, or -1 until found."""
        if self.found:
            return self.value_start
        chunk_start = self._base + len(self._carry)
        window = self._carry + chunk
        match = DISPLAY_KEY_PATTERN.search(window)
        if match:
            self._last_window = window
            self._match_end_in_window = match.end()
            self._chunk_start = chunk_start
            self.value_start = self._base + match.end()
            return self.value_start
        if len(window) > _LOCATOR_CARRY_CHARS:
            drop = len(window) - _LOCATOR_CARRY_CHARS
            self._carry = window[drop:]
            self._base += drop
        else:
            self._carry = window
        return -1

    def offset_in_chunk(self, chunk: str) -> int:
        """Index within the most recently fed ``chunk`` where the value starts.

        Only meaningful on the same feed that discovered the key; -1 when
        the value starts in an earlier chunk or in carried history.
        """
        if not self.found:
            return -1
        rel = self.value_start - self._chunk_start
        return rel if 0 <= rel <= len(chunk) else -1


class DisplayTextChain:
    """Full-stream display extractor: locator → decoder → restart stitching.

    Feeds RAW provider JSON chunks; returns decoded displayText characters
    exactly once. Handles the two supported stream shapes:

    1. first object streams normally (locator + decoder);
    2. a continuation RESTARTS a fresh JSON object: a new ``displayText``
       key appears in the stream (the key may itself split across chunks —
       the scanner carries a bounded buffer until the anchor matches or the
       buffer bound proves it is post-value metadata, which is dropped).

    Post-value JSON metadata (``","spokenText":…"}``, fence closes, other
    keys) never matches the restart anchor and never leaks into the display
    stream. Prose-resumed continuations are intentionally unsupported: the
    runtime's continuation prompt mandates a fresh JSON object (directive
    §18), and finalization parses the complete buffer, so live deltas only
    ever need these two shapes.
    """

    # Bound for the restart-scan buffer: a genuine continuation emits
    # `{"displayText":` within its first few characters; anything longer is
    # post-value metadata and is dropped deterministically.
    RESTART_SCAN_BUFFER_LIMIT = 256

    def __init__(self) -> None:
        self._locator = JsonDisplayTextLocator()
        self._decoder: DisplayTextStreamDecoder | None = None
        self._scan_carry = ""
        self._restart_count = 0

    @property
    def restarts(self) -> int:
        """Number of continuation-restart display values after the first."""
        return self._restart_count

    def feed(self, raw: str) -> str:
        if not raw:
            return ""
        if not self._locator.found:
            start = self._locator.feed(raw)
            if start < 0:
                return ""
            # The key may have completed inside carried history (split key),
            # so slice from the stored match window rather than the chunk.
            raw = self._locator.value_source_text
            if not raw:
                return ""
        if self._decoder is None:
            self._decoder = DisplayTextStreamDecoder()
        if not self._decoder.closed:
            out = self._decoder.feed(raw)
            if self._decoder.closed:
                tail = self._decoder.take_tail()
                if tail:
                    out += self._scan_for_restart(tail)
            return out
        return self._scan_for_restart(raw)

    def _scan_for_restart(self, raw: str) -> str:
        """Buffer-scan for a fresh-object restart anchor; drop other metadata."""
        out = ""
        pending = raw
        while pending:
            self._scan_carry += pending
            pending = ""
            match = DISPLAY_KEY_PATTERN.search(self._scan_carry)
            if match:
                rest = self._scan_carry[match.end() :]
                self._scan_carry = ""
                self._decoder = DisplayTextStreamDecoder()
                self._restart_count += 1
                out += self._decoder.feed(rest)
                if self._decoder.closed:
                    pending = self._decoder.take_tail()
                continue
            if len(self._scan_carry) > self.RESTART_SCAN_BUFFER_LIMIT:
                # No restart anchor: post-value metadata or noise. Dropped.
                self._scan_carry = ""
            break
        return out

    def finish(self) -> str:
        """Flush a pending partial escape at end-of-stream.

        Unmatched scan carry is dropped deterministically: without a restart
        anchor it can only be post-value metadata.
        """
        if self._decoder is None:
            return ""
        return self._decoder.finish()


def decode_display_field(json_text: str) -> str:
    """One-shot: decode the FIRST displayText string value in ``json_text``.

    Uses the same escape-safe decoder as streaming, so completed-buffer
    parsing and streamed decoding agree byte-for-byte.
    """
    match = DISPLAY_KEY_PATTERN.search(json_text)
    if not match:
        return ""
    decoder = DisplayTextStreamDecoder()
    return decoder.feed(json_text[match.end() :])


def decode_all_display_fields(json_text: str) -> list[str]:
    """Decode EVERY displayText value in ``json_text`` in order.

    Used at finalization when a continuation restarted a fresh JSON object
    instead of continuing the first one mid-string: the segments' display
    texts are recovered independently and concatenated by the caller.
    """
    values: list[str] = []
    search_from = 0
    while True:
        match = DISPLAY_KEY_PATTERN.search(json_text, search_from)
        if not match:
            break
        decoder = DisplayTextStreamDecoder()
        values.append(decoder.feed(json_text[match.end() :]))
        # Advance past this key; a nested displayText inside the decoded
        # value is impossible in valid JSON (quotes are escaped there).
        search_from = match.end() + max(1, decoder.emitted_length)
    return values


class AdaptiveStreamDecoder:
    """Incrementally decodes either JSON displayText or raw prose streams escape-safely.

    Feeds chunks from any provider; dynamically detects if the payload begins with JSON
    or markdown/prose. If JSON, extracts and escape-safely decodes only displayText.
    If prose, streams deltas directly.
    """

    def __init__(self) -> None:
        self._mode: str | None = None  # None: undetermined, "json", "prose"
        self._prefix_buffer = ""
        self._chain = DisplayTextChain()
        self._narration = SimulatedToolCallFilter()

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        if self._mode == "prose":
            return self._narration.feed(chunk)
        if self._mode == "json":
            return self._chain.feed(chunk)

        self._prefix_buffer += chunk
        stripped = self._prefix_buffer.lstrip()
        if not stripped:
            return ""

        if stripped.startswith(("{", "```json", "```")):
            self._mode = "json"
            return self._chain.feed(self._prefix_buffer)
        else:
            self._mode = "prose"
            out = self._prefix_buffer
            self._prefix_buffer = ""
            return self._narration.feed(out)

    def finish(self) -> str:
        if self._mode == "json":
            return self._chain.finish()
        if self._mode is None and self._prefix_buffer:
            out = self._prefix_buffer
            self._prefix_buffer = ""
            return self._narration.feed(out) + self._narration.finish()
        if self._mode == "prose":
            return self._narration.finish()
        return ""


# Markup a model writes when it pretends to call a tool in prose. The real call
# goes through the tool pipeline, so anything of this shape in the answer is
# noise that duplicates the card the user is already shown.
_SIMULATED_TOOL_CALL_PATTERN = re.compile(
    r"<\s*(?:" + TOOLISH_TAG_SOURCE + r")[^>]*>.*?<\s*/\s*[A-Za-z][\w:.-]*\s*>",
    re.DOTALL | re.IGNORECASE,
)
_STRAY_TOOL_TAG_PATTERN = re.compile(
    r"<\s*/?\s*(?:" + TOOLISH_TAG_SOURCE + r")[^>]*>?",
    re.IGNORECASE,
)


def strip_simulated_tool_calls(text: str) -> str:
    """Remove tool-call markup a model wrote into its answer.

    Runs over the assembled answer, not a stream delta: an unbalanced tag
    fragment cannot be told apart from real text until the text is complete.
    Code fences are left alone — when the user asks for an example of this
    markup, the markup is the answer.
    """
    if "<" not in text:
        return text
    parts = text.split("```")
    # Even indexes sit outside a fence; odd indexes are fenced code samples.
    scrubbed = [
        part
        if index % 2
        else _STRAY_TOOL_TAG_PATTERN.sub("", _SIMULATED_TOOL_CALL_PATTERN.sub("", part))
        for index, part in enumerate(parts)
    ]
    return "```".join(scrubbed)
