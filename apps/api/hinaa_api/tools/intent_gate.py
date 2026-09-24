"""Who is allowed to decide that a turn is a tool call.

The registry dump in the prompt let whatever brain answered pick tools, so a
flash-tier gateway turned "remind me to call Sile at 4:00" into a referral to
Siri, an isekai recommendation into `image_search Naruto`, a complaint about a
failed image into a new image job, and "stop generating" into another image job.
Every one of those is a routing decision made by a model that has no business
making it.

This module makes the decision with regular expressions instead. The default is
that no tool runs. A tool runs only when the owner's own words name the action,
and the parameters come out of this module rather than out of the model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

from hinaa_api.models import ToolRequest

# Tools the model may never self-assign. Anything outside this set is left alone
# (preferences, artifact lookups, and slash commands are handled elsewhere).
GATED_TOOLS = {
    "image_generate",
    "image_upscale",
    "image_relight",
    "image_search",
    "web_search",
    "web_answer",
    "deep_research",
    "reminder.create",
    "document_generate",
    "pdf_generate",
}

# Gated calls whose every required parameter this module reads out of the owner's
# words. Anything a call still needs from the model — a search query, a document
# topic — is not here, because then the model is choosing the work again.
SELF_SPECIFIED = {
    "image_generate": ("prompt",),
    "reminder.create": ("title", "at"),
}


def _any_kept(kept: list[Any], names: Iterable[str]) -> bool:
    return any(getattr(req, "toolName", None) in names for req in kept)


def _already_kept(kept: list[Any], name: str) -> bool:
    return _any_kept(kept, (name,))


def _selects_asset(parameters: Any) -> bool:
    return isinstance(parameters, dict) and bool(
        parameters.get("reference_images") or parameters.get("reference_asset_id")
    )

IMAGE_NOUNS = (
    r"(?:imges?|images?|imgs?|pictures?|photos?|pics?|pv|pvs|posters?|"
    r"wallpapers?|artworks?|drawings?|sketch(?:es)?|चित्र|तस्वीरें|फोटो)"
)
GENERATE_VERBS = r"(?:generate|genrate|generat|creat(e|ing)?|draw|paint|render|design|make|बनाओ|बनाइए)"
FETCH_VERBS = r"(?:show|sho|display|find|search|get|fetch|bring|see|look\s+for|send\s+me|give\s+me|भेज|दिखा|ढूँढ|खोज|लाओ)"
TIME_UNITS = r"(?:minutes?|mins?|hours?|hrs?|seconds?|days?|weeks?)"

# Verbs that already name a picture. "draw goku" needs no noun to prove it is a
# generation request, while "make" and "create" do.
VISUAL_VERBS = r"(?:draw|paint|render|sketch|illustrate)"
HEAD_VERBS = rf"(?:generate|genrate|generat|creat(?:e|ing)?|{VISUAL_VERBS}|design|make|बना(?:ओ|इए))"
FILLERS = (
    r"(?:please|pls|kindly|can\s+you|could\s+you|would\s+you|will\s+you|"
    r"hey|hi|hello|now|also|just|babe|jaan|baby)"
)
CONNECTORS = r"(?:of|for|featuring|with|showing|depicting|about)"
QUALITY_WORDS = r"(?:ultra|8k|4k|2k|hd|fhd|masterpiece|high\s+quality|best\s+quality)"
COUNT_WORDS = r"(?:two|three|four|five|six|seven|eight|nine|ten)"

# Talking *about* the tools instead of asking for one. A turn that mentions a
# past action, a failure, or an imperative to halt is never a tool request,
# however many nouns from the lists above it happens to contain.
META_FRAMING = re.compile(
    r"""(?ix)
    \b (?:
        why | how\s+come | what\s+happened | didn'?t | dont | don'?t | do\s+not |
        never | stop | quit | cancel | abort | pause | enough | useless | broken |
        fail(?:ed|ing|ure)? | error | wrong | not\s+working | wasn'?t | weren'?t |
        i\s+asked | i\s+wanted | instead\s+of | yesterday | earlier | last\s+time |
        again | supposed | should\s+have | can'?t | cannot | fix | debug |
        suggest | recommend | recommendation | any\s+ideas | what\s+should |
        do\s+you\s+(?:have|support|can) | can\s+you\s+really | is\s+it\s+true
    ) \b
    """
)

ABORT = re.compile(
    r"""(?ix)
    ^ \s*
    (?:
        (?:please\s+|ok(?:ay)?\s+|hey\s+)?
        (?:stop|cancel|abort|pause|quit|halt|never\s+mind|nvm)
        (?:\s+(?:generating|generation|it|that|this|please|the\s+\w+))?\b
      | i\s+(?:didn'?t|did\s+not)\s+ask(?:\s+for)?\b
      | (?:that\s+)?wasn'?t\s+what\s+i\s+asked\b
      | (?:don'?t|do\s+not)\s+(?:generate|create|draw|make|search|fetch)\b
    )
    """
)

SLASH_COMMAND = re.compile(r"^\s*/[a-zA-Z][\w-]*\b")

_REMIND = re.compile(r"(?i)\b(?:remind\s+me|reminder|set\s+(?:a\s+)?(?:reminder|alarm)|wake\s+me)\b")
_WEB = re.compile(
    r"""(?ix) \b (?: search(?:\s+the\s+web|\s+online|\s+for)? | google(?:\s+search)? | look\s+(?:it\s+)?up |
        web\s*search | latest\s+(?:news|episode|release|version|developments?|anime|animes|isekai|\w+) |
        find\s+(?:the\s+)?latest | current\s+(?:news|\w+) | what'?s\s+(?:new|trending|happening) | on\s+the\s+web ) \b"""
)
_RESEARCH = re.compile(r"(?ix)^\s*(?:please\s+)?(?:research|investigate|dig\s+into|look\s+into)\s+\S")
_DOCUMENT = re.compile(
    r"""(?ix) \b (?: pdf | docx? | document(?:s|ation)? | report\s+file | slides? |
        deck | word\s+doc | excel | spreadsheet ) \b"""
)
_DOCUMENT_ASK = re.compile(
    r"(?ix) \b(?:make|create|generate|write|prepare|build|turn\s+\w+\s+into)\b[^.?!]*\b"
    r"(?:pdf|docx?|document|report|deck|slides?|spreadsheet|excel)\b"
)
# Two registered tools build documents and the injector picks between them, so
# "make me a pdf" sanctions the family. Naming one of them would drop the other
# and leave a genuine document request with no tool at all.
_DOCUMENT_FAMILY = frozenset({"document_generate", "pdf_generate"})
_FABRIC_UPSCALE = re.compile(r"(?ix)\b(?:up[\s-]?scal\w*|make\s+it\s+(?:bigger|sharper|4k|8k))\b")
_FABRIC_RELIGHT = re.compile(r"(?ix)\b(?:re-?light\w*)\b")

# "Generate Hina sitting in a cafe" asks for a picture without using the word.
# The lead verb plus a subject we already know is drawable is as explicit as an
# image noun, and unlike a noun mention it cannot be a recommendation ask.
_VISUAL_LEAD = re.compile(
    r"(?ix) ^ \s* (?: hey\s+ )? (?: hinaa? [\s,]+ )? (?: please\s+ )?"
    r"(?: generate | draw | paint | render | create ) \s+ \S"
)
# A variant of the picture he is pointing at. Which picture comes out of the
# selected-asset state, so the sentence itself carries no prompt to extract.
_VARIANT_ASK = re.compile(
    r"(?ix) \b (?: same\s+one | this\s+one | that\s+one | use\s+this | use\s+that ) \b"
    r" .* \b (?: darker | brighter | lighter | softer | sharper | better | different |"
    r" variation | variations | wearing | sitting | standing | looking | smiling | in | with | like ) \b"
)


# A leading visual verb plus a subject we know is drawable is enough on its own,
# but "generate a list of naruto episodes" names a character and still wants
# words. Only an explicit picture noun rescues that ask.
_TEXT_DELIVERABLE = re.compile(
    r"(?ix) \b (?: list | summary | summaries | episode(?:s)? | season(?:s)? | story | essay |"
    r" paragraph | ideas? | names? | code | script | translate | translation | meaning |"
    r" definition | quote(?:s)? | lyrics? | plot | explanation | notes? | article |"
    r" review | wiki | fandom ) \b"
)


def _names_known_subject(lowered: str, known_subjects: Iterable[str]) -> bool:
    for name in ("hina", "hinaa", *known_subjects):
        if name and re.search(rf"(?i)\b{re.escape(name)}\b", lowered):
            return True
    return False


@dataclass
class ToolSanction:
    """What the owner's words authorized, with the parameters they imply."""

    allowed: set[str] = field(default_factory=set)
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Sanctioned calls whose parameters were read out of conversation state
    # rather than out of his sentence, so the planned call is kept as built.
    resolved: set[str] = field(default_factory=set)
    abort: bool = False
    explicit: bool = False

    def permits(self, tool_name: str) -> bool:
        return tool_name in self.allowed


def _allow_document(sanction: ToolSanction) -> None:
    for name in _DOCUMENT_FAMILY:
        sanction.allowed.add(name)
        sanction.parameters[name] = {}


def _subject_after_verb(text: str) -> str | None:
    """The words the action verb is acting on.

    ``None`` means the sentence names no action verb at all; the empty string
    means it names one with nothing after it. The difference matters because
    falling back to the whole sentence is how his complaint ended up as the
    prompt.
    """
    match = re.search(rf"(?ix) \b{HEAD_VERBS}\b", text)
    if not match:
        return None
    return text[match.end() :].strip(" .,;!?")


def _apply(text: str, *patterns: str) -> str:
    out = text
    for pattern in patterns:
        out = re.sub(pattern, " ", out, flags=re.IGNORECASE | re.VERBOSE)
    return re.sub(r"\s+", " ", out).strip(" .,;:!?-")


def extract_image_subject(text: str) -> str | None:
    """The thing to draw, or None when the words don't name one.

    Returning None is the important branch: a failed extraction used to hand the
    vendor his complaint, so the picture came out describing a broken request.
    """
    candidate = _subject_after_verb(text)
    if candidate is None:
        candidate = text.strip(" .,;!?")
    if not candidate:
        return None

    candidate = _apply(
        candidate,
        # "please can you", "for me", "make me a picture" -> the me is not the subject.
        rf"""
        ^ \s* (?: {FILLERS} | for \s+ me | (?:a|an|the) \s+ (?:{IMAGE_NOUNS})
            | me | us | my | our )
        \b [,.]? \s*
        """,
        rf""" ^ \s* (?: {FILLERS} | for \s+ me | me | us ) \b [,.]? \s* """,
        # The batch size first, while the noun it hangs off is still there.
        rf""" \b (?: \d{{1,2}} | {COUNT_WORDS} ) \s+ (?: {IMAGE_NOUNS} ) \b """,
        # Every remaining mention of the medium, with its article and connector:
        # "a picture of", "images", "the wallpaper for".
        rf"""
        (?: \b (?: a | an | the | some | few | couple \s+ of | my ) \s+ )?
        \b (?: {IMAGE_NOUNS} ) \b (?: \s+ {CONNECTORS} \b )? \s*
        """,
        rf""" \b (?: mode | quality | aspect \s+ ratio | ratio ) \s* :? \s*
              \w * (?: - \w+ ) * """,
        QUALITY_WORDS,
        # A trailing style request is instructions for the renderer, not the subject.
        rf"""
        \b (?: in | with | using ) \s+ (?: the \s+ )?
        (?: anime | realistic | cinematic | watercolor | digital | 3d [\s-]* art
          | cyberpunk | ghibli | sketch | oil \s+ painting | oil \s+ colour
          | pencil | pixel \s+ art )
        \b [^.!?]*
        """,
        rf""" (?: {FILLERS} | for \s+ me | too | as \s+ well | now | please )
              \b [,.]? \s* $ """,
    )

    # Whatever the strips left behind can start or end on a word that only made
    # sense next to the noun that was removed: "of a red fox", "cats with".
    for _ in range(4):
        stripped = _apply(
            candidate,
            rf""" ^ \s* (?: {CONNECTORS} | a | an | the | some | my | your | our | me | i
                      | and | that | this | in | to | of ) \b \s* """,
            rf""" \s+ (?: {CONNECTORS} | a | an | the | and | with | to | in | of | for )
                   \b \s* $ """,
        )
        if stripped == candidate:
            break
        candidate = stripped

    if not candidate:
        return None
    words = candidate.split()
    if len(words) > 12 or len(candidate) > 90:
        return None
    if len("".join(words)) < 2:
        return None
    if re.search(r"(?i)\b(?:you|your|i|me|my)\b", candidate) and len(words) > 3:
        return None
    if META_FRAMING.search(candidate):
        return None
    if candidate == candidate.casefold():
        candidate = candidate[0].upper() + candidate[1:]
    return candidate


def requested_count(text: str, *, maximum: int = 10) -> int:
    """How many he asked for. Defaults to one rather than the vendor default."""
    numerals = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    match = re.search(
        rf"(?ix) \b(?:{COUNT_WORDS}|\d{{1,2}}) \b \s* (?: {IMAGE_NOUNS} | variants? | versions? ) \b",
        text or "",
    )
    if not match:
        return 1
    token = match.group(0).split()[0].casefold()
    count = numerals.get(token) or (int(token) if token.isdigit() else 0)
    if count < 1:
        return 1
    return min(count, maximum)


def _reminder_title(text: str, at_phrase: str | None) -> str | None:
    body = re.sub(r"(?i)^\s*(?:please\s+)?(?:remind|set\s+(?:a\s+)?(?:reminder|alarm)|wake)\b", "", text)
    body = re.sub(r"(?i)^\s*(?:me|us)\b", "", body)
    body = re.sub(r"(?i)^\s*(?:to|that|i\s+must|i\s+have\s+to)\b", "", body)
    if at_phrase:
        body = body.replace(at_phrase, " ")
    body = re.sub(r"(?i)\b(?:today|tonight|tomorrow|this\s+(?:morning|afternoon|evening)|at\s+the\s+office|please|pls|babe)\b", " ", body)
    body = re.sub(rf"(?i)\b\d{{1,2}}(?::\d{{2}})?\s*(?:am|pm)?\s*(?:o'?clock|{'TIME_UNITS'})?\b", " ", body)
    body = re.sub(rf"(?i)\bin\s+\d+\s+{TIME_UNITS}\b", " ", body)
    body = re.sub(r"\s+", " ", body).strip(" .,;:!?-")
    # Removing the time can expose the words that introduced the task.
    for _ in range(3):
        trimmed = re.sub(r"(?i)^(?:to|that|about|for|me|us|please)\b\s*", "", body)
        if trimmed == body:
            break
        body = trimmed.strip(" .,;:!?-")
    if not body or len(body.split()) > 12:
        return None
    return body[0].upper() + body[1:]


def _parse_when(text: str, now: datetime) -> tuple[datetime | None, str | None]:
    """Resolve a spoken time to a real datetime, or nothing if it isn't there."""
    specs: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"(?i)\bin\s+(\d+)\s*(minutes?|mins?|hours?|hrs?|days?|weeks?)\b"), "offset"),
        (re.compile(r"(?i)\b(?:by|at|around|@)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b"), "clock"),
        (re.compile(r"(?i)\b(\d{1,2}):(\d{2})\s*(am|pm)?\b"), "clock"),
        (re.compile(r"(?i)\b(\d{1,2})\s*(am|pm)\b"), "clock"),
        (re.compile(r"(?i)\b(?:today|tomorrow)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b"), "clock"),
    ]
    tomorrow = bool(re.search(r"(?i)\btomorrow\b", text))
    for pattern, kind in specs:
        match = pattern.search(text)
        if not match:
            continue
        fields = list(match.groups()) + [None, None, None]
        if kind == "offset":
            amount, unit = int(fields[0]), str(fields[1]).lower()
            unit = unit.rstrip("s")
            if unit.startswith("min"):
                delta = timedelta(minutes=amount)
            elif unit.startswith("h"):
                delta = timedelta(hours=amount)
            elif unit.startswith("d"):
                delta = timedelta(days=amount)
            else:
                delta = timedelta(weeks=amount)
            return now + delta, match.group(0)
        hour, minute = int(fields[0]), int(fields[1] or 0)
        meridiem = str(fields[2] or "").lower()
        if meridiem == "pm" and hour < 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        if not meridiem and 1 <= hour <= 7 and not re.search(r"(?i)\bmorning\b", text):
            # "call Sile at 4:00" is four in the afternoon. The alternative is a
            # reminder that fires in the middle of the night, which is worse than
            # being wrong about a late-night errand nobody phrases this way.
            hour += 12
        if hour > 23 or minute > 59:
            continue
        base = now + timedelta(days=1) if tomorrow else now
        target = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target, match.group(0)
    named = {
        "noon": (12, 0),
        "midnight": (0, 0),
        "tonight": (20, 0),
        "this evening": (18, 0),
        "this afternoon": (15, 0),
        "this morning": (9, 0),
    }
    for phrase, (hour, minute) in named.items():
        if phrase in text.casefold():
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return target, phrase
    return None, None


def sanction_tools(
    text: str,
    *,
    now: datetime | None = None,
    known_subjects: Iterable[str] = (),
) -> ToolSanction:
    """Read the owner's words and return the only tools this turn may run."""
    raw = (text or "").strip()
    sanction = ToolSanction()
    if not raw:
        return sanction

    if ABORT.match(raw):
        sanction.abort = True
        return sanction

    if SLASH_COMMAND.match(raw):
        # He typed the verb the system would otherwise have to infer.
        sanction.explicit = True
        verb = re.match(r"^\s*/([\w-]+)", raw).group(1).casefold()
        mapping = {
            "image": "image_generate",
            "img": "image_generate",
            "draw": "image_generate",
            "generate": "image_generate",
            "pic": "image_search",
            "pics": "image_search",
            "search": "web_search",
            "web": "web_search",
            "google": "web_search",
            "research": "deep_research",
            "deep": "deep_research",
            "pdf": "document_generate",
            "doc": "document_generate",
            "remind": "reminder.create",
        }
        tool = mapping.get(verb)
        if tool in _DOCUMENT_FAMILY:
            _allow_document(sanction)
        elif tool:
            sanction.allowed.add(tool)
            sanction.parameters[tool] = {}
        return sanction

    lowered = raw.casefold()
    has_image_noun = bool(re.search(rf"(?ix) \b{IMAGE_NOUNS} \b", lowered))
    generate_verb = bool(re.search(rf"(?ix) \b{GENERATE_VERBS} \b", lowered))
    fetch_verb = bool(re.search(rf"(?ix) \b{FETCH_VERBS} \b", lowered))
    wants = bool(re.search(r"(?i)\b(?:i\s+(?:want|need)|wanna|gimme|looking\s+for|chahiye|chahe)\b", lowered))

    reminder = _REMIND.search(lowered)
    if reminder:
        when, at_phrase = _parse_when(raw, now or datetime.now())
        title = _reminder_title(raw, at_phrase)
        if when is not None and title:
            sanction.allowed.add("reminder.create")
            sanction.parameters["reminder.create"] = {
                "title": title,
                "at": when.isoformat(timespec="minutes"),
            }
        return sanction

    if _DOCUMENT_ASK.search(lowered) or (_DOCUMENT.search(lowered) and (generate_verb or fetch_verb)):
        if not META_FRAMING.search(lowered):
            _allow_document(sanction)
        return sanction

    if _RESEARCH.search(lowered):
        sanction.allowed.add("deep_research")
        sanction.parameters["deep_research"] = {}
        return sanction

    if _VARIANT_ASK.search(lowered) and not META_FRAMING.search(lowered):
        # "same one but darker" is him pointing at the picture he picked. The
        # action is in his words; which asset and what prompt are in the state
        # our own router resolved before this gate ran, so its call is kept.
        sanction.allowed.add("image_generate")
        sanction.resolved.add("image_generate")
        return sanction

    pure_visual = bool(re.search(rf"(?ix) \b{VISUAL_VERBS} \b", lowered))
    named_subject = (
        bool(_VISUAL_LEAD.match(lowered))
        and not _TEXT_DELIVERABLE.search(lowered)
        and _names_known_subject(lowered, known_subjects)
    )
    if (has_image_noun and generate_verb) or pure_visual or named_subject:
        if not META_FRAMING.search(lowered):
            subject = extract_image_subject(raw)
            if subject:
                sanction.allowed.add("image_generate")
                sanction.parameters["image_generate"] = {
                    "prompt": subject,
                    "count": requested_count(raw),
                }
        return sanction

    if has_image_noun and (fetch_verb or wants) and not META_FRAMING.search(lowered):
        # That he wants existing images is decided here. Which words to search
        # them with is left to the media compiler, which reads the subject out of
        # the conversation rather than out of this one sentence.
        sanction.allowed.add("image_search")
        sanction.parameters["image_search"] = {}
        return sanction

    wants_upscale = bool(_FABRIC_UPSCALE.search(lowered))
    wants_relight = bool(_FABRIC_RELIGHT.search(lowered))
    if (wants_upscale or wants_relight) and not META_FRAMING.search(lowered):
        # These act on the image already in context, so naming the operation is
        # the whole request and no parameter has to be guessed from his prose.
        if wants_upscale:
            sanction.allowed.add("image_upscale")
            sanction.parameters["image_upscale"] = {}
        if wants_relight:
            sanction.allowed.add("image_relight")
            sanction.parameters["image_relight"] = {}
        return sanction

    if _WEB.search(lowered) and not META_FRAMING.search(lowered):
        sanction.allowed.add("web_search")
        sanction.parameters["web_search"] = {}
        return sanction

    return sanction


def gate_tool_requests(
    text: str,
    requests: Iterable[Any],
    *,
    now: datetime | None = None,
    known_subjects: Iterable[str] = (),
) -> tuple[list[Any], list[str], ToolSanction]:
    """Keep the calls the owner asked for, drop the ones a brain invented.

    Two calls the gate can specify completely out of his own words, so it opens
    for those as well as filtering: a reminder he set in a sentence the answering
    brain skimmed is still a reminder he asked for. Search tools are only filtered
    here because their query is compiled downstream from the whole conversation,
    and one guessed from a single sentence would be worse than the planned one.
    """
    planned = list(requests)
    sanction = sanction_tools(text, now=now, known_subjects=known_subjects)
    if sanction.abort:
        return [], [getattr(req, "toolName", "?") for req in planned], sanction

    kept: list[Any] = []
    dropped: list[str] = []
    for req in planned:
        name = getattr(req, "toolName", None)
        if name not in GATED_TOOLS:
            kept.append(req)
            continue
        if name not in sanction.allowed:
            dropped.append(name)
            continue
        if name in _DOCUMENT_FAMILY and _any_kept(kept, _DOCUMENT_FAMILY):
            # Either builder answers the one ask. The action runs, so the extra
            # copy is skipped without telling him a request was refused.
            continue
        if name in sanction.resolved:
            if _already_kept(kept, name):
                continue
            if not _selects_asset(getattr(req, "parameters", None)):
                # Only the call our own router built knows which picture "the
                # same one" is. Unbound, there is nothing to draw.
                dropped.append(name)
                continue
            kept.append(req)
            continue
        authorized = {k: v for k, v in (sanction.parameters.get(name) or {}).items() if v}
        if name in SELF_SPECIFIED:
            if not all(key in authorized for key in SELF_SPECIFIED[name]):
                dropped.append(name)
                continue
            if _already_kept(kept, name):
                # One call carries the batch. The action still runs, so a second
                # planned copy is skipped rather than reported as refused.
                continue
        parameters = getattr(req, "parameters", None)
        if not isinstance(parameters, dict):
            parameters = {}
            req.parameters = parameters
        if name in SELF_SPECIFIED:
            # The subject of a picture and the moment of a reminder are the two
            # parameters a brain got by paraphrasing him. Both leave this module.
            parameters.update(authorized)
        else:
            # Searches keep whatever query the injector resolved, because the
            # media compiler knows more about the subject than these regexes do.
            for key, value in authorized.items():
                parameters.setdefault(key, value)
        kept.append(req)

    for name in sorted(sanction.allowed):
        if name in sanction.resolved:
            # Nothing to open: the subject was the asset the router bound, and
            # if it bound none there is no picture to generate.
            continue
        required = SELF_SPECIFIED.get(name)
        if not required or _already_kept(kept, name):
            continue
        authorized = {k: v for k, v in (sanction.parameters.get(name) or {}).items() if v}
        if not all(key in authorized for key in required):
            continue
        kept.append(
            ToolRequest(
                toolName=name,
                parameters=dict(authorized),
                reason="deterministic-intent",
            )
        )

    # Two different facts get conflated above: a call he never asked for, and a
    # planned copy the gate did not need because the same action already runs.
    # Only the first is a refusal he should be told about.
    kept_names = {getattr(req, "toolName", None) for req in kept}
    dropped = [name for name in dropped if name not in kept_names]
    return kept, dropped, sanction


# A reply that claims work which the gate just refused -- either as a promise or
# as a finished result -- is a lie the owner hears before anything fails to
# arrive, so the sentence goes with the tool.
PROMISE = re.compile(
    r"""(?ix)
    [^.!?]* \b (?: i'?ll | i\s+will | let\s+me | sure[,!]?\s+i | here\s*(?:are|'s) |
        generating | fetching | searching | sending | drawing | creating |
        on\s+it | give\s+me\s+a\s+sec | right\s+away ) \b
    [^.!?]* \b (?: image | pic | picture | photo | wallpaper | art | drawing |
        render | job | result | search | pdf | document | reminder | file ) s? \b
    [^.!?]* [.!?]?
    """
)

# A media search captions itself the moment the router files the call, so the
# past tense here reports work nobody did yet -- and after the gate refuses the
# call, work nobody will do. Measured live: "image generation is broken" answered
# "Found 6 relevant Generation Is Broken images." with no search running.
STALE_CLAIM = re.compile(
    r"""(?ix)
    [^.!?]* \b (?: found | located | retrieved | pulled | fetched | attached |
        gathered | यहाँ ) \b
    [^.!?]* \b (?: image | images | pic | pics | picture | photo | wallpaper |
        render | job | result | results | search | pdf | document | reminder | file |
        तस्वीर | तस्वीरें | चित्र ) \b
    [^.!?]* [.!?]?
    """
)

# One plain sentence per action that will not happen: no pet name, no emoji, no
# apology paragraph. He asked for the format because the alternative was her
# spending four lines explaining herself after doing nothing at all.
BLOCKED_NOTE = {
    "abort": "Stopped. Nothing new was started.",
    "image": "I did not start an image job because your message was not a request for one.",
    "search": "I did not search because your message was not a request to search.",
    "document": "I did not build a document because your message was not a request for one.",
    "reminder": "I did not set a reminder because your message was not a request to set one.",
    # The opposite failure: he did ask, and the sentence named no subject to act
    # on, so telling him his message was not a request would be untrue.
    "unbound": "I don't have the picture you mean, so nothing was started.",
}

TOOL_KIND = {
    "image_generate": "image",
    "image_upscale": "image",
    "image_relight": "image",
    "image_search": "image",
    "web_search": "search",
    "web_answer": "search",
    "deep_research": "search",
    "document_generate": "document",
    "pdf_generate": "document",
    "reminder.create": "reminder",
}


def blocked_note(dropped: list[str], *, aborted: bool = False, unbound: bool = False) -> str:
    if aborted:
        return BLOCKED_NOTE["abort"]
    if unbound and dropped:
        return BLOCKED_NOTE["unbound"]
    for name in dropped:
        kind = TOOL_KIND.get(name)
        if kind:
            return BLOCKED_NOTE[kind]
    return "I did not run that because your message was not a request to run it."


# Deleting a promised sentence leaves its decoration behind. A stranded 🔥 reads
# as the tone he asked a blocked reply not to have, and a stranded ", " or "and"
# reads as a broken sentence.
ORPHAN_EMOJI = r"\U0001F300-\U0001FAFF☀-➿️"
ORPHAN_HEAD = rf"\s.,:;!\-\u2014\u2013\u2018\u2019\u201c\u201d{ORPHAN_EMOJI}"


def strip_stale_promises(text: str) -> str:
    """Remove sentences that claim a tool the gate refused to run, promised or done."""
    if not text:
        return text
    cleaned = PROMISE.sub("", text)
    cleaned = STALE_CLAIM.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s*\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(rf"^\s*(?:and\b|so\b|but\b)\s*|^[{ORPHAN_HEAD}]+", "", cleaned, flags=re.IGNORECASE)
    # Only emoji and whitespace go from the end. The sentence that survived ends
    # with its own full stop, and deleting it would be losing his answer.
    cleaned = re.sub(rf"[\s{ORPHAN_EMOJI}]+$", "", cleaned)
    return cleaned
