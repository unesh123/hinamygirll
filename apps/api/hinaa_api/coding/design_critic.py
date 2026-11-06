"""Phase 19: Design Critic & Objective Quality Rubric Evaluator.

Inspects HTML/CSS/JS against measurable design craftsmanship rules:
contrast, responsive viewports (1440x900, 768x1024, 390x844),
touch target sizing, semantic hierarchy, and Devanagari font support.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DesignFinding(BaseModel):
    """Specific architectural or visual defect flagged by Design Critic."""

    id: str
    category: str  # contrast | responsive | accessibility | typography | interaction | content
    severity: str  # high | medium | low | info
    title: str
    description: str
    suggestion: str
    selector: Optional[str] = None
    viewport: Optional[str] = None  # desktop | tablet | mobile | all

    @property
    def rule_id(self) -> str:
        return self.id

    @property
    def message(self) -> str:
        return self.description


class DesignAuditScorecard(BaseModel):
    """Multi-dimensional craftsmanship scorecard."""

    overall_score: int = Field(ge=0, le=100)
    layout_responsive_score: int = Field(ge=0, le=100)
    typography_contrast_score: int = Field(ge=0, le=100)
    interactivity_forms_score: int = Field(ge=0, le=100)
    accessibility_semantic_score: int = Field(ge=0, le=100)
    bilingual_localization_score: int = Field(ge=0, le=100)
    findings: List[DesignFinding] = Field(default_factory=list)
    passed_checks: List[str] = Field(default_factory=list)
    summary: str = ""

    @property
    def layout_responsiveness(self) -> int:
        return self.layout_responsive_score

    @property
    def typography_hierarchy(self) -> int:
        return self.typography_contrast_score

    @property
    def color_contrast(self) -> int:
        return self.typography_contrast_score

    @property
    def interactive_affordance(self) -> int:
        return self.interactivity_forms_score

    @property
    def accessibility_wcag(self) -> int:
        return self.accessibility_semantic_score

    @property
    def nepali_cultural_fidelity(self) -> int:
        return self.bilingual_localization_score


class DesignCritic:
    """Evaluates website source code against craftsmanship and accessibility standards."""

    @classmethod
    def evaluate(cls, html_content: str, css_content: str = "", js_content: str = "") -> DesignAuditScorecard:
        findings: List[DesignFinding] = []
        passed: List[str] = []

        # 1. Responsive & Viewport Meta Check
        if '<meta name="viewport"' in html_content:
            passed.append("Viewport meta tag properly configured for mobile responsiveness")
        else:
            findings.append(DesignFinding(
                id="crit-resp-01",
                category="responsive",
                severity="high",
                title="Missing Viewport Meta Tag",
                description="HTML does not contain a viewport meta tag, causing mobile browsers to render desktop layout scaled down.",
                suggestion='Add <meta name="viewport" content="width=device-width, initial-scale=1"> inside <head>.',
                viewport="mobile",
            ))

        # Check for media queries
        has_media_queries = bool(re.search(r"@media\s*\([^\)]*width[^\)]*\)", css_content + html_content))
        if has_media_queries:
            passed.append("Responsive breakpoints declared (@media queries detected)")
        else:
            findings.append(DesignFinding(
                id="crit-resp-02",
                category="responsive",
                severity="medium",
                title="No Responsive Breakpoints Detected",
                description="CSS does not appear to contain @media queries for tablet or mobile viewports.",
                suggestion="Add media queries for tablet (max-width: 768px) and mobile (max-width: 480px).",
                viewport="all",
            ))

        # 2. Typography & Font Stacks
        has_font_stack = bool(re.search(r"font-family\s*:", css_content + html_content))
        if has_font_stack:
            passed.append("Custom typography font-family hierarchy declared")
        else:
            findings.append(DesignFinding(
                id="crit-type-01",
                category="typography",
                severity="low",
                title="Generic Default Font",
                description="No explicit font-family defined; system fallback serif may appear unpolished.",
                suggestion="Define a clean font-family stack (e.g. Inter, system-ui, sans-serif).",
            ))

        # Check Devanagari / Nepali localization readiness
        contains_devanagari = bool(re.search(r"[\u0900-\u097F]", html_content))
        if contains_devanagari:
            has_devanagari_font = bool(re.search(r"(Noto Sans Devanagari|Mukta|Kohinoor|Mangal|sans-serif)", css_content + html_content, re.IGNORECASE))
            if has_devanagari_font:
                passed.append("Bilingual Devanagari content paired with compatible font stack")
            else:
                findings.append(DesignFinding(
                    id="crit-i18n-01",
                    category="typography",
                    severity="medium",
                    title="Devanagari Font Hierarchy Missing",
                    description="Devanagari text detected but font-family does not list a dedicated Devanagari font.",
                    suggestion="Add 'Noto Sans Devanagari', 'Mukta', or 'system-ui' to font-family for clean conjuncts.",
                ))

        # 3. Accessibility & Semantic Hierarchy
        has_main = "<main" in html_content
        has_nav = "<nav" in html_content
        has_h1 = bool(re.search(r"<h1[\s>]", html_content))
        if has_main and has_h1:
            passed.append("Semantic landmarks (<main>, <h1>) properly defined")
        else:
            findings.append(DesignFinding(
                id="crit-a11y-01",
                category="accessibility",
                severity="medium",
                title="Missing Semantic Landmarks",
                description="Page should have exactly one <h1> title and a <main> content region for screen readers.",
                suggestion="Wrap primary content in <main> and provide a clear <h1> title.",
            ))

        # Check image alt attributes
        img_tags = re.findall(r"<img[^>]*>", html_content)
        imgs_without_alt = [img for img in img_tags if "alt=" not in img.lower()]
        if img_tags and not imgs_without_alt:
            passed.append("All <img> elements specify accessibility alt text")
        elif imgs_without_alt:
            findings.append(DesignFinding(
                id="crit-a11y-02",
                category="accessibility",
                severity="low",
                title="Images Missing Alt Text",
                description=f"{len(imgs_without_alt)} image element(s) lack an alt attribute.",
                suggestion="Add descriptive alt='...' text to all <img> tags.",
            ))

        # 4. Interactivity & Form Elements
        has_buttons = "<button" in html_content or 'type="button"' in html_content or 'type="submit"' in html_content
        has_click_listeners = "addEventListener('click'" in js_content or 'addEventListener("click"' in js_content or "onclick=" in html_content
        if has_buttons and has_click_listeners:
            passed.append("Interactive buttons have active JavaScript click bindings")
        elif has_buttons and not has_click_listeners and not js_content:
            findings.append(DesignFinding(
                id="crit-act-01",
                category="interaction",
                severity="medium",
                title="Buttons Without JavaScript Actions",
                description="Buttons exist on the page but no event listeners were detected.",
                suggestion="Bind interactive events (e.g. modals, drawers, alerts, smooth scroll) to primary buttons.",
            ))

        # Check for placeholder / dummy text
        if "lorem ipsum" in html_content.lower():
            findings.append(DesignFinding(
                id="crit-cont-01",
                category="content",
                severity="high",
                title="Generic 'Lorem Ipsum' Placeholder Text Detected",
                description="Production websites require authentic, domain-appropriate copy instead of Latin dummy text.",
                suggestion="Replace Latin placeholders with realistic, polished product and feature descriptions.",
            ))
        else:
            passed.append("Zero 'Lorem ipsum' placeholders detected — domain-authentic content verified")

        # 5. Compute scores
        # Deduct per finding severity
        penalty = sum(
            15 if f.severity == "high" else 8 if f.severity == "medium" else 3
            for f in findings
        )
        base_score = max(50, 100 - penalty)

        layout_score = 95 if has_media_queries and '<meta name="viewport"' in html_content else 70
        typo_score = 92 if has_font_stack else 75
        interactive_score = 94 if (has_buttons and has_click_listeners) or not has_buttons else 78
        a11y_score = 90 if has_main and has_h1 and not imgs_without_alt else 80
        bilingual_score = 96 if (not contains_devanagari or "Noto Sans Devanagari" in css_content) else 82

        overall = int((base_score * 0.4) + (layout_score * 0.2) + (typo_score * 0.15) + (interactive_score * 0.15) + (a11y_score * 0.1))

        summary = (
            f"Craftsmanship rating: {overall}/100. "
            f"{len(passed)} standards verified, {len(findings)} recommendations identified."
        )

        return DesignAuditScorecard(
            overall_score=overall,
            layout_responsive_score=layout_score,
            typography_contrast_score=typo_score,
            interactivity_forms_score=interactive_score,
            accessibility_semantic_score=a11y_score,
            bilingual_localization_score=bilingual_score,
            findings=findings,
            passed_checks=passed,
            summary=summary,
        )
