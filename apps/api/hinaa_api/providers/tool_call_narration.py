"""Streaming filter for tool-call markup a model writes into its prose.

`strip_simulated_tool_calls` can only run over a finished answer. These deltas
reach the screen and the voice queue as they arrive, so a model that narrates a
call it is not making leaks the markup to the reader — and a sentence of XML is
what her voice then reads aloud. The tag is only recognisable a few characters
in, so the fragment has to be held back rather than emitted.
"""

from __future__ import annotations

import re

_TAG_HEAD_PATTERN = re.compile(r"<\s*(/?)\s*([A-Za-z][\w:.-]*)")
# One structural rule, exported so the final-answer scrubber uses the same
# definition. Three live turns in a row invented the same call in a different
# spelling, and an enumeration loses one every time.
TOOLISH_TAG_SOURCE = (
    r"(?:(?:tool|function|antml)[_.:-][\w:.-]+"
    r"|(?:tool|function)(?:calls?|args?|names?|uses?|results?|parameters?|arguments?)"
    r"|calls?|invokes?|parameters?|arguments?|tooluse)"
)
_TOOLISH_NAME_PATTERN = re.compile(
    "^" + TOOLISH_TAG_SOURCE + "$",
    re.IGNORECASE,
)
# A model that is role-playing a call closes its own block; anything still
# swallowed past this is real prose and gets through intact.
_MAX_SWALLOW_CHARS = 4_000
# A start tag longer than this is not a tag — "<" used as a less-than sign.
_MAX_TAG_HOLD_CHARS = 64
# Longest closing tag that must survive being split across two deltas.
_MAX_CLOSER_HOLD_CHARS = 64


def _is_toolish(name: str) -> bool:
    return bool(_TOOLISH_NAME_PATTERN.fullmatch(name.replace("-", "_")))


class SimulatedToolCallFilter:
    """Drop invented tool-call elements from a text stream, tag by tag.

    Opening and closing names are matched case-insensitively but not by
    identity: models that invent this markup close `<tool_call>` with
    `</toolCall>` just as often as not.
    """

    def __init__(self) -> None:
        self._held = ""
        self._closer: re.Pattern[str] | None = None
        self._swallowed = 0

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        self._held += chunk
        emitted: list[str] = []

        while self._held:
            if self._closer is not None:
                match = self._closer.search(self._held)
                if match is None:
                    # Provider deltas split tags anywhere, so a tail has to
                    # survive for the next scan or a closer is never reassembled.
                    retained = self._held[-_MAX_CLOSER_HOLD_CHARS :]
                    self._swallowed += len(self._held) - len(retained)
                    self._held = retained
                    if self._swallowed > _MAX_SWALLOW_CHARS:
                        self._closer = None
                    break
                self._swallowed += match.end()
                self._held = self._held[match.end() :]
                self._closer = None
                continue

            index = self._held.find("<")
            if index < 0:
                emitted.append(self._held)
                self._held = ""
                break
            if index:
                emitted.append(self._held[:index])
                self._held = self._held[index:]

            end = self._held.find(">")
            if end < 0:
                if len(self._held) > _MAX_TAG_HOLD_CHARS:
                    # A "<" that never becomes a tag is just text.
                    emitted.append("<")
                    self._held = self._held[1:]
                    continue
                break  # provider deltas split tag names anywhere

            tag = self._held[: end + 1]
            head = _TAG_HEAD_PATTERN.match(tag)
            if head is None or not _is_toolish(head.group(2)):
                emitted.append(tag)
                self._held = self._held[len(tag) :]
                continue
            if head.group(1):
                # A stray closer with no opener is itself the whole markup.
                self._held = self._held[len(tag) :]
                continue
            self._closer = re.compile(r"<\s*/\s*[A-Za-z][\w:.-]*\s*>")
            self._swallowed = 0
            self._held = self._held[len(tag) :]

        return "".join(emitted)

    def finish(self) -> str:
        """Release whatever was held back once the stream is over."""
        held, self._held = self._held, ""
        self._closer = None
        return held
