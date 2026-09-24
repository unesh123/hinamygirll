"""LaTeX must never reach a surface that cannot typeset it.

Reproduced on the live streaming endpoint (23 Sep 2026): a chemistry turn came
back as ``$$6\\text{CO}_2 + 6\\text{H}_2\\text{O} \\xrightarrow{\\text{light energy}} ...$$``.
The frontend renders markdown through ``react-markdown`` with no math plugin and
KaTeX is not a dependency, so that markup shows its own characters. Nothing in
her system can typeset, so conversion happens on the way out.
"""

import random
import re

from hinaa_api.prompts.fallback import neutral_fallback_plan
from hinaa_api.response.notation import MathNotationStream, ascii_math, plainify_math
from hinaa_api.services import _apply_response_quality_guard

PHOTOSYNTHEESIS = (
    "**Balanced Chemical Equation:**\n\n"
    "$$6\\text{CO}_2 + 6\\text{H}_2\\text{O} \\xrightarrow{\\text{light energy}}"
    " \\text{C}_6\\text{H}_{12}\\text{O}_6 + 6\\text{O}_2$$\n\n"
    "Want me to break down the stages?"
)
QUADRATIC = r"The quadratic formula is $x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$ and it solves any equation."

# Captured verbatim from a live reply (23 Sep 2026). Invented fixtures paired
# their `$` delimiters too neatly around whole formulas, so they never exposed the
# bug below. This one puts three jobs on adjacent signs: a formula opener, a
# closing sign that is really the start of a price, and bare prices in a table row.
COMPOUND_INTEREST = (
    "* **Year 0:** A = 1000 (1 + 0.05/1)⁽¹⁾⁽⁰⁾ = $1,000.00\n"
    "* **Year 1:** $A = 1000 (1 + 0.05/1)⁽¹⁾⁽¹⁾ = 1000 × 1.05 = $1,050.00$\n"
    "* **Year 2:** $A = 1000 (1 + 0.05/1)⁽¹⁾⁽²⁾ = 1000 × (1.05)² = $1,102.50$\n"
    "| **Year 1** | $1,000.00 | $50.00 | $1,050.00 |"
)

MARKUP = re.compile(r"\$\$?|\\[A-Za-z]|\^\{|_\{")


def _plan(display: str, spoken: str | None = None):
    plan = neutral_fallback_plan(user_text="hello", companion_id="hinaa", language="mixed")
    plan.displayText = display
    plan.spokenText = spoken if spoken is not None else display
    return plan


def test_guard_ships_no_latex_to_the_bubble() -> None:
    plan = _plan(PHOTOSYNTHEESIS)

    _apply_response_quality_guard(plan)

    assert not MARKUP.search(plan.displayText), plan.displayText
    assert "6CO₂ + 6H₂O" in plan.displayText
    assert "C₆H₁₂O₆ + 6O₂" in plan.displayText


def test_guard_ships_the_quadratic_formula_as_readable_text() -> None:
    plan = _plan(QUADRATIC)

    _apply_response_quality_guard(plan)

    assert not MARKUP.search(plan.displayText), plan.displayText
    assert "(-b ± √(b² - 4ac))/2a" in plan.displayText


def test_voice_gets_the_ascii_form_of_the_same_expression() -> None:
    """A speech engine guessing at `H₂O` and `—light energy→` is not a voice."""
    plan = _plan(PHOTOSYNTHEESIS)

    _apply_response_quality_guard(plan)

    assert "₂" not in plan.spokenText
    assert "→" not in plan.spokenText
    assert "6CO2 + 6H2O" in plan.spokenText
    assert "light energy gives" in plan.spokenText


def test_conversion_is_idempotent() -> None:
    """Both channels run through here more than once in a turn."""
    for text in (PHOTOSYNTHEESIS, QUADRATIC):
        once = plainify_math(text)
        assert plainify_math(once) == once


def test_money_and_identifiers_survive() -> None:
    """An unbacked `$...$` is a price, and `report_2024` is not a subscript."""
    prose = "It costs $5 today and $10 tomorrow. Read report_2024 and column user_name."
    assert plainify_math(prose) == prose
    assert plainify_math("Pay $2, $3, or $4 now.") == "Pay $2, $3, or $4 now."


def test_bare_symbol_names_convert_too() -> None:
    """Measured on the live quadratic turn: the formula came out readable and the
    bullet list under it still said `$x$`, because a lone variable carries none of
    the operator evidence a price check looks for.
    """
    bullets = (
        "- **$x$**: the unknown. "
        "- **$a, b,$ and $c$**: the coefficients, where a != 0."
    )

    out = plainify_math(bullets)

    assert "$" not in out, out
    assert "**x**: the unknown" in out
    assert "**a, b, and c**" in out


def test_latex_currency_escapes_convert_and_keep_their_sign() -> None:
    """Measured live: `$\\$10,000$` shipped as typed because the escaped `$` read
    as the span's closing delimiter, splitting one money value into three prices.
    """
    money = r"For an investment of $\$10,000$ at $8\%$ over a $10$-year period."
    out = plainify_math(money)

    assert "\\$" not in out and "\\%" not in out and "$$" not in out, out
    assert "$10,000" in out and "8%" in out and "10-year" in out


def test_bare_numbers_convert_where_a_price_does_not() -> None:
    """A compounding table wrote its `n` column as `**$1$**`, `**$365$**`; the
    same reply says `$12,500` means money. The rule bets that a price never
    closes with `$`, so a comma stays protected and a closed span converts.
    """
    table = "| **$1$** | Annually | $\\$21,589.25$ |\n| **$365$** | Daily | x |"
    out = plainify_math(table)

    assert "**1**" in out and "**365**" in out and "$21,589.25" in out, out
    assert "\\$" not in out and "$$" not in out, out
    assert plainify_math("The fee is $12,500 flat.") == "The fee is $12,500 flat."


def test_the_bare_number_bet_costs_a_sign_in_a_money_list() -> None:
    """The price of the rule above, written down where changing it must pay for it.

    `the range is $5, $10$ dollars` reads as two amounts to a person, but only
    the second closes with `$`, so it is indistinguishable from `$12$` meaning a
    12-month period. Converting spends one sign; refusing spends the markup that
    `$1$`, `$12$`, `$365$` need. Both readings cannot be honoured, so this is a
    standing trade-off rather than a bug -- flip it knowingly, not by accident.
    """
    out = plainify_math("the range is $5, $10$ dollars")

    assert out == "the range is $5, 10 dollars", out
    assert plainify_math(out) == out


def test_short_assignments_convert_where_prose_does_not() -> None:
    """Live reply: "annually ($n=1$), semi-annually ($n=2$)". A previous rule
    rejected those for being longer than two characters, which is a word count
    accident -- `n=12` spells nothing, and that is what a price does.
    """
    live = r"Frequencies include annually ($n=1$), quarterly ($n=4$), monthly ($n=12$)."
    out = plainify_math(live)

    assert "(n=1)" in out and "(n=4)" in out and "(n=12)" in out, out
    assert "$" not in out, out
    assert plainify_math("Use the $5 bill for the app and $6 for the tax.") == (
        "Use the $5 bill for the app and $6 for the tax."
    )


def test_equations_and_bracketed_powers_convert() -> None:
    """Live: `$I = Prt$` and `$(a+b)^2$` both shipped their markup. Neither carries
    a command, so the evidence has to be structural -- an equals sign with symbols
    on both sides, and a `^` whose base is a closing bracket.
    """
    out = plainify_math(
        "Simple interest is $I = Prt$, and the binomial $(a+b)^2 = a^2 + 2ab + b^2$ expands."
    )

    assert "I = Prt" in out and "(a+b)² = a² + 2ab + b²" in out, out
    assert "$" not in out, out
    assert plainify_math("The ($5) note is rare.") == "The ($5) note is rare."


def test_a_long_dollar_pair_never_becomes_math() -> None:
    """Live reply named `$5,000$` twice, and the pair formed between the two
    unrelated mentions carried an `=` from the prose in the middle. Evidence alone
    cannot tell that apart from an equation; length can, and deleting two real
    currency signs is content loss, not a cosmetic miss.
    """
    prose = (
        "The retainer is $5,000 and, after the audit plus the follow-up sessions "
        "the consultant recommended (scope = 12 pages) during the quarter, the "
        "second engagement is $5,000 too."
    )
    assert plainify_math(prose) == prose
    assert len(prose.split("$")[1]) > 64, "the cap, not the evidence, is what saves it"


def test_a_numeric_computation_converts_where_two_prices_do_not() -> None:
    """Live: the binomial turn ended by shipping `$9 + 24 + 16$` as typed. Nothing
    in that body is an equation, a script or a command, so only the shape of the
    whole span can tell a computation from money -- and money keeps its signs.
    """
    out = plainify_math("So $(3+4)^2$ is $9 + 24 + 16$ = 49.")
    assert "(3+4)² is 9 + 24 + 16 = 49." in out, out
    assert "$" not in out, out
    for money in (
        "It costs $1,200 + $300 = $1,500 all in.",
        "The fee is $12,500 and the deposit $2,000 = 15000 to pay.",
    ):
        assert plainify_math(money) == money, money


def test_windows_paths_and_regex_escapes_are_not_rewritten() -> None:
    """`\\Users` is not a LaTeX command; eating its backslash turns a path into prose."""
    prose = r"Put it in C:\Users\unesh\new and match \d+ or \w+ in regex."
    assert plainify_math(prose) == prose


def test_fenced_code_keeps_its_latex_verbatim() -> None:
    """A reply that shows him markup on purpose must stay copy-pasteable."""
    source = "Try this:\n```python\nx = 5  # $\\text{CO}_2$\ny = a_1 ^ 2\n```\ndone"
    assert plainify_math(source) == source


def test_malformed_markup_costs_no_content() -> None:
    """Truncated output degrades to the raw text, never to a dropped number."""
    assert plainify_math(r"So $$x = \frac{1") == r"So $$x = \frac{1"


def test_a_truncated_command_does_not_hang() -> None:
    """`group()` skipped whitespace with `peek() in " \t"`, which is True at end
    of string -- a `\frac` at the end of a delta spun forever and wedged the worker.
    """
    assert plainify_math("solve \\frac ") == "solve \\frac "


CORPUS = (
    PHOTOSYNTHEESIS,
    QUADRATIC,
    r"Euler: \(e^{i\pi} + 1 = 0\) done.",
    r"\[\int_0^1 x^2 dx = \frac{1}{3}\] and then text.",
    r"$\begin{pmatrix} a & b \\ c & d \end{pmatrix}$ trailing",
    r"$\frac{\sqrt{x+1}}{x-2} = 3$ for x.",
    "It costs $5, so use $x^2 + y^2 = z^2$ here.",
    "Only $$99 for the pair, thanks!",
    "Run `git status` then use $a^2 + b^2 = c^2$ next.",
    "For $\\alpha = 0.05$ and $\\pi r^2$ the area is 3.14.",
    "The value x_1 and then y^2 at the end_3",
    "हिन्दी में $\\alpha + \\beta$ और अंग्रेज़ी।",
    "| a | b |\n|---|---|\n| $x^2$ | 2 |\nend",
    "Try:\n```python\nx = 5  # $\\text{CO}_2$\n```\ndone",
    r"So $$x = \frac{1",
    "Watch out for the \\ path tail",
    "Code:\n```python\nx = $a_1$\ny = b^2\n```\nAnd $\\alpha$ after.",
    "Unclosed fence:\n```python\nx = 5 ^ 2\nstill open",
    "Title\n\n\n\nBody with $x^2$ here.",
    "No math at all.\n\n\n\nJust extra blank lines.",
    "- **$x$**: the unknown.\n- **$a, b,$ and $c$**: coefficients, a != 0.\n"
    "Discriminant $b^2 - 4ac$ decides.",
    r"Invest $\$10,000$ at $8\%$ and earn $\$666.13$ more.",
    "Frequencies include annually ($n=1$), quarterly ($n=4$), monthly ($n=12$) and $1,080.00 paid.",
    "Simple interest is $I = Prt$, and $(a+b)^2 = a^2 + 2ab + b^2$ expands; the ($5) note is rare.",
    "| n | Mode | Value |\n|---|---|---|\n| **$1$** | Annual | $\\$21,589.25$ |\n"
    "| **$365$** | Daily | $\\$22,255.38$ |\nend",
    "The retainer is $5,000 and, after the audit plus the follow-up sessions "
    "the consultant recommended (scope = 12 pages) during the quarter, the "
    "second engagement is $5,000 too.",
    "So $(3+4)^2$ is $9 + 24 + 16$ = 49 and it costs $1,200 + $300 = $1,500 all in.",
    COMPOUND_INTEREST,
    "the range is $5, $10$ dollars and Pay $2, $3, or $4 now.",
)


def _reassemble(text: str, size: int) -> str:
    stream = MathNotationStream()
    parts = [text[i : i + size] for i in range(0, len(text), size)]
    return "".join(stream.feed(p) for p in parts) + stream.flush()


def test_streamed_chunks_equal_the_one_shot_conversion() -> None:
    """The bubble types whatever lands in it, so the chunked path may not disagree
    with the guard by a single character at any delta boundary.
    """
    for text in CORPUS:
        want = plainify_math(text)
        for size in range(1, len(text) + 1):
            assert _reassemble(text, size) == want, (text[:40], size)


def test_random_delta_boundaries_do_not_leak_markup() -> None:
    rng = random.Random(20260923)
    for text in CORPUS:
        want = plainify_math(text)
        for _ in range(200):
            parts: list[str] = []
            i = 0
            while i < len(text):
                step = rng.randint(1, 9)
                parts.append(text[i : i + step])
                i += step
            stream = MathNotationStream()
            got = "".join(stream.feed(p) for p in parts) + stream.flush()
            assert got == want, (text[:40], parts[:4])


def test_flush_ships_a_construct_that_never_resolved() -> None:
    """Held-back text is a delay, not a deletion: a truncated reply still lands."""
    stream = MathNotationStream()
    head = stream.feed(r"Equation: $$6\text{CO}_2 + 6\text{H}_2")
    tail = stream.flush()

    assert head == "Equation: "
    assert "CO" in tail and "H" in tail
    assert stream.buffer == ""


def test_a_leading_exponent_is_fixed_at_commit_not_while_typing() -> None:
    """The one boundary the sweep could not close, kept honest on purpose.

    Whether an undelimited `^{2}` is mathematics depends on a real command
    appearing somewhere in the reply, and the delta that carries it has already
    been sent by then. So the typed text lags by that one construct; what the
    bubble commits -- the text he keeps, copies and saves -- is converted.
    """
    source = r"^{2}y = 3 and \alpha arrives later"
    stream = MathNotationStream()
    typed = "".join(stream.feed(source[:i]) for i in range(1, len(source) + 1))
    typed += stream.flush()
    committed = plainify_math(source)

    assert "^{2}" in typed
    assert "α" in committed and "^{2}" not in committed
    assert not MARKUP.search(committed), committed


def test_a_fence_only_counts_when_it_opens_its_line() -> None:
    """CommonMark says so, and the converter must not disagree with the renderer
    or with the streaming hold-back -- that decides what counts as code.
    """
    midline = "Set the flag ``x^{2}`` inline please."
    assert plainify_math(midline) == midline


def test_a_price_is_never_spent_to_close_a_formula() -> None:
    """The one defect here that could destroy content instead of exposing markup.

    `$A = ... = $1,050.00$` has no reading in which all three signs are
    delimiters, and the earlier pairing rule took the formula's opener and the
    final sign, deleting the currency one: `=1,050.00$`. A stray `$` around a
    formula costs her typesetting she never had; a missing one rewrites an amount
    she was asked to report.
    """
    converted = plainify_math(COMPOUND_INTEREST)

    assert converted.count("$") == COMPOUND_INTEREST.count("$")
    for amount in ("$1,000.00", "$1,050.00", "$1,102.50", "$50.00"):
        assert converted.count(amount) == COMPOUND_INTEREST.count(amount), amount
    assert plainify_math(converted) == converted


def test_a_currency_sign_escaped_inside_math_still_converts() -> None:
    r"""The other direction: `\$` is how a model writes a price inside math mode,
    so the money rule must not swallow the span that legitimately contains one.
    """
    source = r"$A = 1000 \times 1.61834 = \$1,161.83$"

    assert plainify_math(source) == "A = 1000 × 1.61834 = $1,161.83"
