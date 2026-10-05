"""Streaming filter for tool-call markup a model writes into its prose.

`strip_simulated_tool_calls` can only run over a finished answer. These deltas
reach the screen and the voice queue as they arrive, so a model that narrates a
call it is not making leaks the markup to the reader — and a sentence of XML is
what her voice then reads aloud. The tag is only recognisable a few characters
in, so the fragment has to be held back rather than emitted.
"""

from __future__ import annotations

import re

_TAG_HEAD_PATTERN = re.compile(r"<\s*(/?)\s*(?:\|)?\s*([A-Za-z][\w:.-]*)")
# ChatML delimiters are a spelling of the same invented markup: `<|tool_call|>`.
_SPECIAL_TOKEN_PATTERN = re.compile(r"<\|([A-Za-z][\w:.-]*)\|>")
# One structural rule, exported so the final-answer scrubber uses the same
# definition. Three live turns in a row invented the same call in a different
# spelling, and an enumeration loses one every time.
TOOLISH_TAG_SOURCE = (
    r"(?:(?:tool|function|antml)[_.:-][\w:.-]+"
    r"|(?:tool|function)(?:calls?|args?|names?|uses?|results?|parameters?|arguments?)"
    r"|calls?|invokes?|parameters?|arguments?|tooluse"
    r"|(?:web_)?search(?:_query)?|search_web|web_research|web_extract|web_answer|google_search)"
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
        self._to_end = False
        self._in_tool_block = False
        self._tool_brace_depth = 0
        self._swallow_trailing_fence = False

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""
        if self._to_end:
            self._held = ""
            return ""
        self._held += chunk
        emitted: list[str] = []

        while self._held:
            if self._swallow_trailing_fence:
                self._held = self._held.lstrip(" \t\r\n")
                if self._held.startswith("```"):
                    post_fence = self._held.find("\n", 3)
                    if post_fence != -1:
                        self._held = self._held[post_fence + 1:].lstrip()
                    else:
                        self._held = self._held[3:].lstrip()
                    self._swallow_trailing_fence = False
                    continue
                elif self._held:
                    self._swallow_trailing_fence = False

            if self._in_tool_block:
                brace_pos = self._held.find("{")
                if brace_pos >= 0 or self._tool_brace_depth > 0:
                    start_i = brace_pos if self._tool_brace_depth == 0 else 0
                    end_pos = -1
                    for i in range(start_i, len(self._held)):
                        if self._held[i] == "{":
                            self._tool_brace_depth += 1
                        elif self._held[i] == "}":
                            self._tool_brace_depth -= 1
                            if self._tool_brace_depth == 0:
                                end_pos = i + 1
                                break
                    if end_pos != -1:
                        tail = self._held[end_pos:end_pos + 20]
                        bt_m = re.search(r"^\s*`{3,}", tail)
                        if bt_m:
                            end_pos += bt_m.end()
                            self._swallow_trailing_fence = False
                        else:
                            self._swallow_trailing_fence = True
                        self._held = self._held[end_pos:].lstrip()
                        self._in_tool_block = False
                        self._tool_brace_depth = 0
                        continue
                    else:
                        self._held = ""
                        break
                else:
                    bt_m = re.search(r"^\s*`{3,}", self._held)
                    if bt_m:
                        self._held = self._held[bt_m.end():].lstrip()
                        self._in_tool_block = False
                        continue
                    break

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

            # Check for simulated TOOL_REQUEST or standalone tool call on prose wire
            tr_match = re.search(r"(?i)\bTOOL_REQUEST\b", self._held)
            standalone_json_match = re.search(
                r'(?is)\{\s*"(?:tool|name|function)"\s*:\s*"(?:web_search|search|web_research)',
                self._held,
            )

            start_tool_idx = -1
            if tr_match:
                start_tool_idx = tr_match.start()
            elif standalone_json_match:
                start_tool_idx = standalone_json_match.start()

            lt_idx = self._held.find("<")

            if start_tool_idx >= 0 and (lt_idx < 0 or start_tool_idx < lt_idx):
                preceding = self._held[:start_tool_idx]
                backtick_idx = preceding.rfind("```")
                if backtick_idx != -1 and all(c in " \t\r\n" for c in preceding[backtick_idx + 3:]):
                    if backtick_idx > 0:
                        emitted.append(self._held[:backtick_idx])
                elif start_tool_idx > 0:
                    emitted.append(self._held[:start_tool_idx])

                self._held = self._held[start_tool_idx:]
                if tr_match and self._held.upper().startswith("TOOL_REQUEST"):
                    self._held = self._held[len("TOOL_REQUEST"):].lstrip()
                self._in_tool_block = True
                self._tool_brace_depth = 0
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
            special = _SPECIAL_TOKEN_PATTERN.fullmatch(tag)
            if special is not None:
                if not _is_toolish(special.group(1)):
                    emitted.append(tag)
                    self._held = self._held[len(tag) :]
                    continue
                # A model that is role-playing a call closes its own block; a
                # model writing a real one never emits the closer, so what
                # follows is the arguments of a call the pipeline makes itself.
                self._to_end = True
                self._held = ""
                break
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
        if re.search(r"(?i)\bTOOL_REQUEST\b", held):
            held = re.sub(r"(?is)(?:`{3,}[^\S\n]*[A-Za-z0-9_-]*[ \t]*\r?\n[ \t]*)?\bTOOL_REQUEST\b[\s\S]*", "", held).strip()
        held = re.sub(r"[ \t]*`{3,}[^\S\n]*\r?\n?[ \t]*`{3,}", "", held).strip()
        return held
