"""Turn model-emitted math markup into text a human can read.

Her words reach four surfaces: the chat bubble, the voice synthesiser, saved
artifacts and notifications. None of them can typeset -- ``react-markdown`` is
loaded without a math plugin and KaTeX is not a dependency at all -- so a brain
that answers a chemistry question with ``$\\text{CO}_2$`` does not show carbon
dioxide. It shows those exact characters.

``plainify_math`` therefore rewrites the markup into Unicode that reads correctly
on every surface at once ("6CO₂ + 6H₂O -light energy→ C₆H₁₂O₆ + 6O₂") instead of
betting on a renderer that does not exist. It is deliberately narrow: it only
fires on delimited math, on unmistakable LaTeX commands, and on element-style
subscripts, so money ("$5 and $10"), identifiers (``file_2``, ``user_name``) and
fenced code survive untouched.

``MathNotationStream`` applies the same conversion to a token stream, holding
back a trailing partial construct until the next chunk resolves it.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_SUB_DIGITS = "₀₁₂₃₄₅₆₇₈₉"
_SUP_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹"

_SUBSCRIPTABLE = {
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ", "l": "ₗ",
    "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ", "s": "ₛ", "t": "ₜ",
    "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    **{d: _SUB_DIGITS[int(d)] for d in "0123456789"},
}

_SUPERSCRIPTABLE = {
    "a": "ᵃ", "b": "ᵇ", "c": "ᶜ", "d": "ᵈ", "e": "ᵉ", "f": "ᶠ", "g": "ᵍ",
    "h": "ʰ", "i": "ⁱ", "j": "ʲ", "k": "ᵏ", "l": "ˡ", "m": "ᵐ", "n": "ⁿ",
    "o": "ᵒ", "p": "ᵖ", "q": "ᵠ", "r": "ʳ", "s": "ˢ", "t": "ᵗ", "u": "ᵘ",
    "v": "ᵛ", "w": "ʷ", "x": "ˣ", "y": "ʸ", "z": "ᶻ",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    **{d: _SUP_DIGITS[int(d)] for d in "0123456789"},
}

# Longest name wins, so `\oint` is not eaten by `\in`.
_SYMBOLS: dict[str, str] = {
    # Greek
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "omicron": "ο", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
    "upsilon": "υ", "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ",
    "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ",
    "Psi": "Ψ", "Omega": "Ω",
    # Relations and operators
    "times": "×", "div": "÷", "cdot": "·", "ast": "∗", "star": "⋆",
    "pm": "±", "mp": "∓", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
    "neq": "≠", "ne": "≠", "approx": "≈", "equiv": "≡", "sim": "∼",
    "simeq": "≃", "cong": "≅", "propto": "∝", "ll": "≪", "gg": "≫",
    "doteq": "≐", "subset": "⊂", "subseteq": "⊆", "supset": "⊃",
    "supseteq": "⊇", "notin": "∉", "ni": "∋", "cup": "∪", "cap": "∩",
    "setminus": "∖", "emptyset": "∅", "varnothing": "∅", "forall": "∀",
    "exists": "∃", "nexists": "∄", "neg": "¬", "lnot": "¬", "wedge": "∧",
    "land": "∧", "vee": "∨", "lor": "∨", "oplus": "⊕", "otimes": "⊗",
    "perp": "⊥", "parallel": "∥", "angle": "∠", "triangle": "△",
    "square": "□", "diamond": "◇", "therefore": "∴", "because": "∵",
    "in": "∈", "circ": "∘", "bullet": "•",
    # Arrows
    "to": "→", "rightarrow": "→", "longrightarrow": "→",
    "rightharpoonup": "⇀", "leftarrow": "←", "gets": "←",
    "leftrightarrow": "↔", "Longleftrightarrow": "⇔", "Rightarrow": "⇒",
    "Longrightarrow": "⟹", "Leftarrow": "⇐", "mapsto": "↦",
    "uparrow": "↑", "downarrow": "↓", "nearrow": "↗", "searrow": "↘",
    "swarrow": "↙", "nwarrow": "↖", "implies": "⟹", "iff": "⟺",
    # Big operators and named functions
    "infty": "∞", "partial": "∂", "nabla": "∇", "sum": "∑", "prod": "∏",
    "coprod": "∐", "int": "∫", "iint": "∬", "iiint": "∭", "oint": "∮",
    "lim": "lim", "limsup": "lim sup", "liminf": "lim inf", "max": "max",
    "min": "min", "sup": "sup", "inf": "inf", "log": "log", "ln": "ln",
    "lg": "lg", "exp": "exp", "sin": "sin", "cos": "cos", "tan": "tan",
    "cot": "cot", "sec": "sec", "csc": "csc", "arcsin": "arcsin",
    "arccos": "arccos", "arctan": "arctan", "sinh": "sinh", "cosh": "cosh",
    "tanh": "tanh", "det": "det", "dim": "dim", "ker": "ker", "deg": "deg",
    "gcd": "gcd", "mod": "mod", "bmod": "mod", "pmod": "mod",
    # Dots and spacing
    "ldots": "…", "cdots": "⋯", "vdots": "⋮", "ddots": "⋱", "dots": "…",
    "quad": "  ", "qquad": "    ",
    # Units and glyphs
    "degree": "°", "textdegree": "°", "celsius": "°C", "degreeCelsius": "°C",
    "kelvin": "K", "angstrom": "Å", "checkmark": "✓", "dagger": "†",
    "copyright": "©", "trademark": "™",
}

# Only glyphs `_walk` can actually produce; a voice engine says these, not them.
_SPOKEN_GLYPHS = {
    "°C": " degrees Celsius",
    "⇌": "reversibly forms", "→": "gives", "←": "goes back to", "↔": "balances with",
    "±": "plus or minus", "≈": "about", "≤": "at most", "≥": "at least",
    "≠": "is not equal to", "×": "times", "÷": "divided by", "√": "square root of",
    "∫": "the integral of", "∑": "the sum of", "∞": "infinity", "π": "pi",
    "°": " degrees", "·": " times ",
}

# Single-character commands: `\,` `\;` `\:` `\!` `\ ` `\%` ...
_CHAR_COMMANDS: dict[str, str] = {
    ",": " ", ";": " ", ":": " ", "!": "", " ": " ", "*": " ",
    "%": "%", "$": "$", "#": "#", "&": "&", "_": "_",
    "{": "{", "}": "}", "|": "|", "@": "@", "`": "'", "^": "",
    "’": "'", "‘": "'",
}

# Commands that put a label on an arrow: `\xrightarrow{light energy}`.
_ARROW_COMMANDS = {
    "xrightarrow": "→", "rightarrow": "→", "longrightarrow": "→",
    "Rightarrow": "⇒", "leftarrow": "←", "xleftarrow": "←",
    "leftrightarrow": "↔", "xleftrightarrow": "↔", "uparrow": "↑",
    "downarrow": "↓", "mapsto": "↦",
}

_ACCENTS = {
    "hat": "\u0302", "widehat": "\u0302", "tilde": "\u0303",
    "widetilde": "\u0303", "bar": "\u0305", "overline": "\u0305",
    "vec": "\u20d7", "dot": "\u0307", "ddot": "\u0308", "check": "\u030c",
    "acute": "\u0301", "grave": "\u0300", "breve": "\u0306",
}

# Commands whose only job is to wrap text in a font: keep the words.
_TEXT_LIKE = {
    "text", "textrm", "textsf", "texttt", "textmd", "textup", "textit",
    "emph", "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "mathbb",
    "boldsymbol", "mathbold", "operatorname", "mbox", "hbox", "textnormal",
    "substack",
}

_FRACS = {"frac", "dfrac", "tfrac", "cfrac"}
_DELIMS = {"left", "right", "big", "Big", "bigg", "Bigg", "bigl", "bigr",
           "Bigl", "Bigr", "biggl", "biggr", "Biggl", "Biggr", "middle",
           "langle", "rangle"}
_CODE_SPANS = re.compile(
    # CommonMark: a fence opens a line, and so does its closing marker. The
    # streaming hold-back has to recognize exactly this or a delta boundary
    # decides whether her code was code.
    r"^[ \t]*(?:`{3,}|~{3,})[^\n]*(?:\n[\s\S]*?(?:^[ \t]*(?:`{3,}|~{3,})|\Z))?"
    r"|`[^`\n]+`",
    re.MULTILINE,
)
_MATH_SPAN = re.compile(
    r"\$\$(?P<display>[\s\S]+?)\$\$"
    # `\$` inside a span is LaTeX for a currency sign, not the end of the span.
    # Reading it as a delimiter split `$\$10,000$` into three fake prices.
    #
    # A closing `$` followed by a digit is a price, not a delimiter. A live reply
    # wrote `$A = 1000 (1 + 0.05/1)... = 1000 × 1.05 = $1,050.00$`, and pairing the
    # formula's opener with the currency sign deleted it: `=1,050.00$`. Refusing the
    # pair costs her the markup around a formula; accepting it costs a real amount.
    r"|(?<!\\)\$(?P<inline>(?:\\.|[^\\\n$])+?)(?<!\\)\$(?![0-9])"
    r"|\\\((?P<paren>[\s\S]+?)\\\)"
    r"|\\\[(?P<bracket>[\s\S]+?)\\\]"
)
# An unbacked `$...$` is money, not math. This is what keeps "$5 and $10" safe.
# A backslash that is not followed by a letter is proof of LaTeX: `\$` and `\%`
# are how a model writes a dollar sign and a percent sign inside math mode.
_MATH_EVIDENCE = re.compile(
    r"\\[A-Za-z]"                       # any real command
    r"|\\[^A-Za-z\s]"                   # `\$` `\%` -- LaTeX punctuation escapes
    r"|_\{|\^\{"                        # an explicit script group
    r"|[A-Za-z0-9_\)\]][_^][A-Za-z0-9{(]"  # a script, incl. `(a+b)^2`
    r"|[A-Za-z0-9\)\]]\s*=\s*[A-Za-z0-9(\[\\]"  # an equation or assignment
    r"|^\s*="                               # a formula continued in its own span
    r"|^\([\dA-Za-z+\-*/^_.,()= ]+\)$"  # a binomial like `(a+b)`
)

# A reply that names its variables writes `$x$`, `$a, b,$ and $c$`, `($n=12$)` with
# nothing inside that proves it is mathematics. What separates those from a price is
# local to the span -- it starts with a symbol and never spells out a word -- so the
# rule can be applied per delta without the reply around it.
_INLINE_SYMBOLS = re.compile(r"[A-Za-z][A-Za-z0-9+\-.,=() ]{0,18}[A-Za-z0-9).,]?")
_ALPHABETIC_WORD = re.compile(r"[A-Za-z]{3,}")


def _is_symbol_list(body: str) -> bool:
    inner = body.strip()
    if not _INLINE_SYMBOLS.fullmatch(inner):
        return False
    return not _ALPHABETIC_WORD.search(inner)


# The same reply put its compounding periods in a table as `$1$`, `$12$`,
# `$365$`. A span holding nothing but a number states a value, so it converts.
#
# This is a bet, not a proof: it assumes a price never closes with `$`. Written
# as a list -- `the range is $5, $10$ dollars` -- the second amount does close
# with one and loses its sign. Both readings cannot be honoured at once, and the
# shapes on the left come from her real replies, so the rule keeps them.
_BARE_NUMBER = re.compile(r"\d{1,6}|\d+\.\d+")


def _is_math_number(body: str) -> bool:
    return bool(_BARE_NUMBER.fullmatch(body.strip()))


# `$9 + 24 + 16$` states a computation. Two real prices in one sentence always
# have a word between them, so requiring the *whole* body to be numbers and
# operators keeps `$1,200 + $300 = $1,500` alone: none of those bodies has an
# operator with a digit on both sides.
_ARITHMETIC_BODY = re.compile(r"[\d\s+\-*/^=().,]+")
_ARITHMETIC_STEP = re.compile(r"\d\s*[+\-*/^]\s*\d")


def _is_arithmetic(body: str) -> bool:
    inner = body.strip()
    if not _ARITHMETIC_BODY.fullmatch(inner):
        return False
    return bool(_ARITHMETIC_STEP.search(inner))


@dataclass
class _Reader:
    src: str
    pos: int = 0

    def at_end(self) -> bool:
        return self.pos >= len(self.src)

    def peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        return self.src[idx] if idx < len(self.src) else ""

    def group(self) -> str:
        """Body of the `{...}` starting at `pos`, or `''` if there is none."""
        while self.peek() in (" ", "\t"):
            self.pos += 1
        if self.peek() != "{":
            return ""
        depth = 0
        for idx in range(self.pos, len(self.src)):
            if self.src[idx] == "{":
                depth += 1
            elif self.src[idx] == "}":
                depth -= 1
                if depth == 0:
                    body = self.src[self.pos + 1 : idx]
                    self.pos = idx + 1
                    return body
        body = self.src[self.pos + 1 :]
        self.pos = len(self.src)
        return body

    def optional_group(self) -> str:
        """`{...}` if present, else the single next character."""
        body = self.group()
        if body:
            return body
        if self.at_end():
            return ""
        ch = self.src[self.pos]
        self.pos += 1
        return ch


def _render_script(body: str, table: dict[str, str]) -> str:
    inner = _walk(body).strip()
    if not inner:
        return ""
    mapped = [table.get(ch) for ch in inner]
    if all(ch is not None for ch in mapped):
        return "".join(mapped)  # type: ignore[arg-type]
    marker = "_" if table is _SUBSCRIPTABLE else "^"
    return f"{marker}({inner})"


# A single term needs no parentheses under a slash. `x-2` is two terms (the `-`
# is binary), `-b` is one (the `-` is unary), `√(x+1)` is already delimited.
_ATOMIC_TERM = re.compile(r"[-+]?(?:[A-Za-z0-9_.]+|√\([^()]*\))")


def _needs_wrapping(expr: str) -> bool:
    return not _ATOMIC_TERM.fullmatch(expr.strip())


def _render_fraction(numerator: str, denominator: str) -> str:
    top = _walk(numerator).strip()
    bottom = _walk(denominator).strip()
    if _needs_wrapping(top):
        top = f"({top})"
    if _needs_wrapping(bottom):
        bottom = f"({bottom})"
    return f"{top}/{bottom}"


def _render_chem(body: str) -> str:
    """mhchem writes formulas compactly: every digit after a letter is a count."""
    out: list[str] = []
    for idx, ch in enumerate(body):
        prev = body[idx - 1] if idx else ""
        if ch.isdigit() and (
            prev.isalpha() or (prev.isdigit() and out and out[-1] in _SUB_DIGITS)
        ):
            out.append(_SUB_DIGITS[int(ch)])
        else:
            out.append(ch)
    text = "".join(out)
    for arrow, glyph in (("->", "→"), ("<->", "⇌"), ("=", "⇌")):
        text = text.replace(arrow, glyph)
    return text


def _read_command(reader: _Reader) -> str:
    """The command name after the backslash; `reader` ends just past it."""
    start = reader.pos + 1
    if start >= len(reader.src):
        reader.pos = start
        return ""
    ch = reader.src[start]
    if ch.isalpha():
        end = start
        while end < len(reader.src) and reader.src[end].isalpha():
            end += 1
        reader.pos = end
        return reader.src[start:end]
    reader.pos = start + 1
    return ch


def _walk(src: str, *, prose: bool = False) -> str:
    """Convert one math body, recursing through nested commands and groups.

    ``prose`` marks a whole reply rather than a delimited span: there an
    ampersand is punctuation a person typed, not a matrix column separator.
    """
    if not src:
        return ""
    reader = _Reader(src)
    out: list[str] = []
    last_pos = -1
    while not reader.at_end():
        # Markup a model invented can outrank every rule above. Rather than let
        # one forgotten `pos += 1` hang his turn, force a character through.
        if reader.pos == last_pos:
            out.append(reader.peek())
            reader.pos += 1
        last_pos = reader.pos
        ch = reader.peek()

        if ch == "\\":
            cmd_start = reader.pos
            name = _read_command(reader)
            if not name:
                out.append("\\")
                continue
            if name == "\\":
                out.append("\\\\" if prose else "; ")
                continue
            if name in _CHAR_COMMANDS:
                out.append(_CHAR_COMMANDS[name])
                continue
            if name in _TEXT_LIKE:
                out.append(_walk(reader.group()))
                continue
            if name in _FRACS:
                num = reader.optional_group()
                den = reader.optional_group()
                # A half-written `\frac{1}` must not cost him the `1`.
                raw = src[cmd_start : reader.pos]
                out.append(_render_fraction(num, den) if num and den else raw)
                continue
            if name in ("sqrt", "nth"):
                root = ""
                if reader.peek() == "[":
                    close = src.find("]", reader.pos)
                    if close != -1:
                        root = _walk(src[reader.pos + 1 : close]).strip()
                        reader.pos = close + 1
                body = reader.optional_group()
                inner = _walk(body).strip()
                if inner:
                    out.append(f"{root}\u221a({inner})" if root else f"\u221a({inner})")
                continue
            if name in ("binom", "dbinom", "tbinom"):
                first = reader.optional_group()
                second = reader.optional_group()
                out.append(f"C({_walk(first).strip()}, {_walk(second).strip()})")
                continue
            if name in _ACCENTS:
                body = reader.optional_group()
                inner = _walk(body).strip()
                if inner:
                    out.append(inner + _ACCENTS[name])
                continue
            if name in _ARROW_COMMANDS:
                glyph = _ARROW_COMMANDS[name]
                label = ""
                under = ""
                if name.startswith("x"):
                    if reader.peek() == "{":
                        label = _walk(reader.group()).strip()
                    if reader.peek() == "[":
                        close = src.find("]", reader.pos)
                        if close != -1:
                            under = _walk(src[reader.pos + 1 : close]).strip()
                            reader.pos = close + 1
                parts = "".join(x for x in (label, under) if x)
                out.append(f"—{parts}{glyph}" if parts else glyph)
                continue
            if name in _DELIMS:
                nxt = reader.peek()
                if nxt == ".":
                    reader.pos += 1
                elif nxt and nxt != "\\":
                    out.append(nxt)
                    reader.pos += 1
                continue
            if name in ("overline", "underline"):
                out.append(_walk(reader.group()))
                continue
            if name == "ce":
                out.append(_render_chem(reader.group()))
                continue
            if name in ("begin", "end"):
                reader.group()
                continue
            if name in ("displaystyle", "textstyle", "limits", "nolimits"):
                continue
            if name in _SYMBOLS:
                out.append(_SYMBOLS[name])
                continue
            # Not a command this converter knows. Keep it exactly as written:
            # deleting the backslash from `C:\Users` would turn a path into prose.
            out.append("\\" + name)
            continue

        if ch == "_":
            reader.pos += 1
            out.append(_render_script(reader.optional_group(), _SUBSCRIPTABLE))
            continue
        if ch == "^":
            reader.pos += 1
            out.append(_render_script(reader.optional_group(), _SUPERSCRIPTABLE))
            continue
        if ch == "{":
            if prose:
                reader.pos += 1
                out.append("{")
                continue
            out.append(_walk(reader.group()))
            continue
        if ch == "}":
            reader.pos += 1
            out.append("}" if prose else "")
            continue
        if ch == "&":
            reader.pos += 1
            out.append(" " if not prose else "&")
            continue
        out.append(ch)
        reader.pos += 1

    text = "".join(out)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" +([,.;:!?])", r"\1", text)
    # A math body's padding is noise; a reply's is the space joining sentences.
    return text if prose else text.strip()


def _element_subscript(text: str) -> str:
    """`CO_2` -> `CO₂` for element-style tokens only, never `file_2`."""
    def repl(match: re.Match[str]) -> str:
        digits = match.group("sub")
        if len(digits) > 3:
            return match.group(0)
        return match.group("token") + "".join(_SUB_DIGITS[int(d)] for d in digits)

    return re.sub(
        r"(?:(?<=[^A-Za-z0-9_])|^)(?P<token>(?:[A-Z][a-z]?\d*){1,6})_(?P<sub>\d{1,3})(?![A-Za-z0-9_])",
        repl,
        text,
    )


def _simple_exponent(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        body = match.group(1) or match.group(2) or ""
        mapped = [_SUPERSCRIPTABLE.get(ch) for ch in body]
        if all(m is not None for m in mapped) and mapped:
            return "".join(mapped)  # type: ignore[arg-type]
        return f"^{body}"

    return re.sub(r"(?<=[A-Za-z0-9])\^(?:\{([A-Za-z0-9+\-]{1,4})\}|([A-Za-z0-9]))", repl, text)


_MAX_INLINE_SPAN = 64


def _replace_span(match: re.Match[str]) -> str:
    for group in ("display", "bracket", "paren", "inline"):
        body = match.group(group)
        if body is None:
            continue
        if group == "inline":
            # A pair of dollar signs can straddle two unrelated prices in one
            # sentence. Real inline math is short, so the length is checked
            # before any evidence rule: a long prose body can never be
            # rewritten no matter what it happens to contain.
            if len(body) > _MAX_INLINE_SPAN:
                return match.group(0)
            if not (
                _MATH_EVIDENCE.search(body)
                or _is_symbol_list(body)
                or _is_math_number(body)
                or _is_arithmetic(body)
            ):
                return match.group(0)
        if group in ("display", "bracket") and not _DISPLAY_EVIDENCE.search(body):
            return match.group(0)
        converted = _walk(body)
        # No blank lines are added here on purpose. The run a display block needs
        # is already in the reply around it, and injecting one would make this
        # span's output depend on newlines that a streamed chunk sent earlier.
        return converted
    return match.group(0)


# `$$` usually means a display equation, but an ad writes "for $$50!" just as
# happily, so the body has to look like mathematics before it is rearranged.
_DISPLAY_EVIDENCE = re.compile(
    _MATH_EVIDENCE.pattern
    + r"|[A-Za-z0-9]\s*[=<>≠≤≥]\s*[A-Za-z0-9]|\d\s*[+\-*/^]\s*\d"
)

# Every command `_walk` gives a meaning to. Prose is only handed to it when one
# of these actually appears, so `\Users`, `\d` and `\n` inside a path or a regex
# cannot trigger a rewrite of the whole reply.
_KNOWN_COMMANDS = frozenset(
    frozenset(_SYMBOLS)
    | frozenset(_ARROW_COMMANDS)
    | frozenset(_ACCENTS)
    | _TEXT_LIKE
    | _FRACS
    | _DELIMS
    | {
        "ce", "sqrt", "nth", "binom", "dbinom", "tbinom", "begin", "end",
        "overline", "underline", "displaystyle", "textstyle", "limits",
        "nolimits", "stackrel", "colon", "quad", "qquad",
    }
)
_LATEX_MARKER = re.compile(
    r"\\[(\[]|\\(?:" + "|".join(map(re.escape, sorted(_KNOWN_COMMANDS))) + r")(?![A-Za-z])"
)

_POSSIBLE_MATH = re.compile(r"\$\$?|\\[A-Za-z(\[]|[A-Za-z0-9]_\{?[A-Za-z0-9]|[A-Za-z0-9]\^")
_ELEMENT_OR_POWER = re.compile(r"[A-Za-z]_[\dA-Za-z{]|[A-Za-z0-9]\^")
_BLANK_RUNS = re.compile(r"\n{3,}")


def _collapse_blank_lines(text: str) -> str:
    """Squeeze a run of empty lines down to one, the way the renderer would.

    This is not part of the math pass: it has to run on text with nothing to
    convert too, because streamed replies are converted in chunks and only the
    chunk that holds a whole blank-line run can tell that it is one.
    """
    return _BLANK_RUNS.sub("\n\n", text)


def plainify_math(text: str) -> str:
    """Rewrite LaTeX-ish math in ``text`` into readable Unicode.

    Fenced and inline code stay byte-for-byte as written, because a reply that
    shows him LaTeX on purpose must remain copy-pasteable. A span that merely
    happens to sit between two dollar signs is money, so "$5 and $10" survives
    too. The result carries no `$`, no backslash command and no `_{}` marker,
    which makes it safe to run twice.
    """
    if not text:
        return text
    if not _POSSIBLE_MATH.search(text):
        return _collapse_blank_lines(text)

    kept: list[str] = []

    def stash(match: re.Match[str]) -> str:
        kept.append(match.group(0))
        return f"\u0000P{len(kept) - 1}\u0000"

    guarded = _CODE_SPANS.sub(stash, text)
    guarded = _MATH_SPAN.sub(_replace_span, guarded)
    # Whatever survives is markup the brain wrote without delimiters. Only a real
    # command triggers the prose pass; `C:\Users` and `\d+` in a regex do not.
    if _LATEX_MARKER.search(guarded):
        guarded = _walk(guarded, prose=True)
    guarded = _element_subscript(guarded)
    guarded = _simple_exponent(guarded)
    # A display block that already sat between blank lines leaves a run behind.
    guarded = _collapse_blank_lines(guarded)
    for idx, chunk in enumerate(kept):
        guarded = guarded.replace(f"\u0000P{idx}\u0000", chunk)
    return guarded


def ascii_math(text: str) -> str:
    """Fold converted math back to characters a speech engine will say plainly.

    ``plainify_math`` output reads correctly on screen, but ``H₂O`` and
    ``—light energy→`` leave a voice engine guessing, so the spoken channel gets
    the ASCII form of the same expression instead.
    """
    if not text:
        return text
    folded = unicodedata.normalize("NFKC", text)
    folded = re.sub(r"—([^—\s][^—]*)→", r" \1 gives ", folded)
    for glyph, word in _SPOKEN_GLYPHS.items():
        folded = folded.replace(glyph, f" {word} ")
    return re.sub(r"\s{2,}", " ", folded)


@dataclass
class MathNotationStream:
    """Feed provider deltas in, get back text that is safe to put on the wire.

    A token can straddle two deltas -- `$\\text{CO` then `_2}$` -- so anything
    that might still grow is held in ``buffer`` and flushed once resolved. Without
    this the bubble types out half a construct and the client has no way to
    recover it.
    """

    buffer: str = ""

    def feed(self, delta: str) -> str:
        if not delta:
            return ""
        self.buffer += delta
        cut = _settled_through(self.buffer)
        if cut == 0:
            return ""
        chunk, self.buffer = self.buffer[:cut], self.buffer[cut:]
        return plainify_math(chunk)

    def flush(self) -> str:
        tail, self.buffer = self.buffer, ""
        return plainify_math(tail)


# Each pattern matches a construct that begins somewhere in the buffer and is
# still growing at its end, so converting what precedes it is safe but converting
# the construct itself would commit to an interpretation the next delta may
# contradict. They are anchored with \Z on purpose. Anything that has to be
# *paired* is handled by a function below instead -- a regex cannot tell an
# opening delimiter from a closing one.
_STILL_TYPING: tuple[re.Pattern[str], ...] = (
    re.compile(r"\\[A-Za-z]+\{(?:[^{}]|\{[^{}]*\})*\Z"),  # command mid-argument
    re.compile(r"\\[A-Za-z]*\Z", re.MULTILINE),           # command name still typing
    re.compile(r"[_^]\{[^{}]*\Z"),                        # script brace still open
    re.compile(r"[_^][A-Za-z0-9+\-]{0,3}\Z"),             # short script, e.g. `_2` -> `_24`
    re.compile(r"^[ \t]*(?:`{1,2}|~{1,2})\Z", re.MULTILINE),  # fence marker half-arrived
)

_FENCE_LINE = re.compile(r"[ \t]*(?:```|~~~)")


def _is_escaped(buf: str, idx: int) -> bool:
    """Whether ``buf[idx]`` sits at the end of an odd run of backslashes."""
    backslashes = 0
    pos = idx - 1
    while pos >= 0 and buf[pos] == "\\":
        backslashes += 1
        pos -= 1
    return backslashes % 2 == 1


def _next_dollar(buf: str, start: int) -> int:
    """Next ``$`` that is a real delimiter, skipping LaTeX's ``\\$`` escape."""
    pos = buf.find("$", start)
    while pos != -1 and _is_escaped(buf, pos):
        pos = buf.find("$", pos + 1)
    return pos


def _dollar_hold(buf: str) -> int | None:
    """Index of a `$` that opened a span which has not closed yet."""
    pos = 0
    while pos < len(buf):
        if buf[pos] != "$" or _is_escaped(buf, pos):
            pos += 1
            continue
        if buf.startswith("$$", pos):
            close = buf.find("$$", pos + 2)
            if close == -1:
                return pos
            pos = close + 2
            continue
        close = _next_dollar(buf, pos + 1)
        newline = buf.find("\n", pos + 1)
        if close == -1:
            # Either the body is still arriving, or it already crossed a line
            # break, which inline math never does. Only the first can still change.
            return pos if newline == -1 else None
        if newline != -1 and newline < close:
            pos = close + 1
            continue
        if close == len(buf) - 1:
            # Whether this pair is math or money turns on the character after the
            # closing sign, and it has not arrived yet.
            return pos
        if buf[close + 1].isdigit():
            # The matcher refuses this pair, and a refused pair does not consume its
            # delimiter: the same sign can open the next span. Resume there.
            pos = close
            continue
        pos = close + 1
    return None


def _tex_delim_hold(buf: str) -> int | None:
    """Index of a `\\(` / `\\[` whose partner has not arrived."""
    stack: list[tuple[int, str]] = []
    for match in re.finditer(r"\\[()\[\]]", buf):
        token = match.group(0)
        if token in ("\\(", "\\["):
            stack.append((match.start(), ")" if token == "\\(" else "]"))
        elif stack and token == "\\" + stack[-1][1]:
            stack.pop()
    return stack[0][0] if stack else None


def _fence_hold(buf: str) -> int | None:
    """Index of the opening marker of a code block that is still open.

    Her code has to reach him exactly as written, and a fence body that streams
    out in pieces would lose its protecting marker on every chunk after the first.
    """
    open_at: int | None = None
    offset = 0
    for line in buf.split("\n"):
        if _FENCE_LINE.match(line):
            open_at = None if open_at is not None else offset
        offset += len(line) + 1
    return open_at


def _complete_span_cut(buf: str, cut: int) -> int:
    """Step back rather than ship half of a finished span.

    A `$...$` converts as a unit and a fenced block must stay byte-for-byte, so a
    chunk carrying only one side of either would leak its delimiters to the bubble.
    """
    for pattern in (_CODE_SPANS, _MATH_SPAN):
        for match in pattern.finditer(buf):
            if match.start() < cut < match.end():
                cut = match.start()
    return cut


def _word_start(buf: str, cut: int) -> int:
    idx = cut
    while idx > 0 and not buf[idx - 1].isspace():
        idx -= 1
    return idx


def _settled_through(buf: str) -> int:
    """Length of the prefix that no future delta can change the meaning of."""
    if not buf:
        return 0
    holds = [p for p in (_dollar_hold(buf), _tex_delim_hold(buf), _fence_hold(buf)) if p is not None]
    holds.extend(m.start() for pattern in _STILL_TYPING for m in pattern.finditer(buf))
    cut = min(holds) if holds else len(buf)
    # Every converter here reads what sits *before* a marker, so a chunk that
    # starts mid-word cannot see its own context: `y` then `^2` would ship `y^2`.
    cut = _word_start(buf, cut)
    cut = _complete_span_cut(buf, cut)
    # Blank lines are squeezed by whatever call can see a whole run, so a run may
    # not be split between two chunks: hold it back until the text after it lands.
    while cut > 0 and buf[cut - 1] == "\n":
        cut -= 1
    return cut
