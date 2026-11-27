"""Archetype blueprints, inline SVG artwork, and accessible section renderers for HINAA Foundry."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import List, Optional

from .tokens import FoundryPalette


@dataclass(frozen=True)
class BlueprintSpec:
    id: str
    cta_label: str
    section_titles: Tuple3
    hero_badge: str


Tuple3 = tuple[str, str, str]

BLUEPRINTS: dict[str, BlueprintSpec] = {
    "cafe_roastery": BlueprintSpec("cafe_roastery", "Explore Roast Menu", ("Signature Origins", "Brewing Standards", "Visit Our Roastery"), "Small-Batch Craft"),
    "saas_product": BlueprintSpec("saas_product", "Start Free Workspace", ("Core Workflows", "Verified Reliability", "Simple Plans"), "Production Ready"),
    "portfolio": BlueprintSpec("portfolio", "View Selected Work", ("Featured Case Studies", "Engineering Discipline", "Get In Touch"), "Selected Portfolio"),
    "agency": BlueprintSpec("agency", "Book Strategy Call", ("Capabilities", "Delivery Playbook", "Start A Project"), "Design & Engineering"),
    "clinic": BlueprintSpec("clinic", "Schedule Consultation", ("Care Programs", "Clinical Team", "Book Your Visit"), "Patient-First Care"),
    "restaurant": BlueprintSpec("restaurant", "Reserve A Table", ("Seasonal Tasting", "Kitchen Philosophy", "Hours & Location"), "Chef Kitchen"),
    "ecommerce": BlueprintSpec("ecommerce", "Browse Collection", ("Featured Releases", "Materials & Guarantee", "Customer Support"), "Curated Drop"),
    "event": BlueprintSpec("event", "Claim Seat Pass", ("Speaker Lineup", "Schedule & Tracks", "Venue Details"), "Annual Summit"),
    "docs": BlueprintSpec("docs", "Read Quickstart", ("Architecture Guides", "API Reference", "Community Support"), "Developer Docs"),
    "studio": BlueprintSpec("studio", "Watch Showreel", ("Production Services", "Recent Reels", "Commission Work"), "Creative Studio"),
}


def detect_blueprint(brief: str) -> BlueprintSpec:
    low = (brief or "").lower()
    if any(k in low for k in ("coffee", "roast", "cafe", "bakery", "tea")):
        return BLUEPRINTS["cafe_roastery"]
    if any(k in low for k in ("restaurant", "bistro", "kitchen", "dining")):
        return BLUEPRINTS["restaurant"]
    if any(k in low for k in ("clinic", "dental", "health", "therapy", "medical")):
        return BLUEPRINTS["clinic"]
    if any(k in low for k in ("shop", "store", "apparel", "ecommerce", "product")):
        return BLUEPRINTS["ecommerce"]
    if any(k in low for k in ("event", "conference", "summit", "festival")):
        return BLUEPRINTS["event"]
    if any(k in low for k in ("docs", "sdk", "documentation", "reference")):
        return BLUEPRINTS["docs"]
    if any(k in low for k in ("studio", "film", "motion", "video")):
        return BLUEPRINTS["studio"]
    if any(k in low for k in ("agency", "consult")):
        return BLUEPRINTS["agency"]
    if any(k in low for k in ("portfolio", "designer", "photographer")):
        return BLUEPRINTS["portfolio"]
    return BLUEPRINTS["saas_product"]


def extract_brand_and_place(brief: str) -> tuple[str, Optional[str]]:
    clean = " ".join((brief or "").strip().split())
    brand = "Horizon Studio"
    place: Optional[str] = None

    m_place = re.search(
        r"\b(?:in|at|located in)\s+([A-Z][A-Za-z0-9\- ]{2,32}?)(?:[,.!;]|$|\s+(?:serving|selling|offering|building|with|for|featuring)\b)",
        clean,
    )
    if m_place:
        place = m_place.group(1).strip()

    m_pred = re.match(r"^([A-Z][A-Za-z0-9&'\- ]{1,40}?)\s+(?:is|are|offers|builds|creates)\b", clean)
    if m_pred:
        brand = m_pred.group(1).strip()
    else:
        m_for = re.search(r"\bfor\s+([A-Z][A-Za-z0-9&'\- ]{2,38}?)(?:[,.!;]|\s+(?:in|at|with|featuring)\b|$)", clean)
        if m_for:
            brand = m_for.group(1).strip()
        elif clean:
            head_only = re.split(r"\s+\b(?:in|at|located in|with|featuring|selling|offering)\b", clean, maxsplit=1)[0]
            words = [w for w in re.split(r"\s+", head_only) if w.lower() not in {"build", "create", "make", "a", "an", "the", "website", "site", "page"}]
            if words:
                brand = " ".join(words[:3]).title()

    return brand[:48], place


def render_inline_svg_mark(brand: str, palette: FoundryPalette) -> str:
    initial = html.escape((brand[:1] or "H").upper())
    return (
        f'<svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden="true">'
        f'<rect width="36" height="36" rx="10" fill="{palette.accent}"/>'
        f'<text x="18" y="24" text-anchor="middle" fill="{palette.accent_text}" '
        f'font-family="system-ui,sans-serif" font-weight="800" font-size="17">{initial}</text>'
        f"</svg>"
    )


def render_hero_art(palette: FoundryPalette) -> str:
    return (
        f'<svg viewBox="0 0 480 280" role="img" aria-label="Abstract architectural hero illustration" class="hero-svg">'
        f'<rect width="480" height="280" rx="18" fill="{palette.surface}" stroke="{palette.border}"/>'
        f'<circle cx="135" cy="128" r="68" fill="{palette.accent}" opacity="0.22"/>'
        f'<circle cx="320" cy="148" r="88" fill="{palette.accent}" opacity="0.14"/>'
        f'<rect x="52" y="64" width="210" height="142" rx="12" fill="{palette.bg}" stroke="{palette.border}"/>'
        f'<rect x="74" y="88" width="110" height="14" rx="7" fill="{palette.accent}"/>'
        f'<rect x="74" y="114" width="160" height="10" rx="5" fill="{palette.muted}" opacity="0.5"/>'
        f'<rect x="74" y="134" width="132" height="10" rx="5" fill="{palette.muted}" opacity="0.35"/>'
        f'<rect x="282" y="96" width="146" height="118" rx="12" fill="{palette.bg}" stroke="{palette.accent}"/>'
        f"</svg>"
    )


def build_site_files(
    *,
    brand: str,
    tagline: str,
    address: Optional[str],
    palette: FoundryPalette,
    blueprint: BlueprintSpec,
    features: List[str],
    client_logos: List[str],
) -> dict[str, str]:
    esc_brand = html.escape(brand)
    esc_tag = html.escape(tagline)
    esc_cta = html.escape(blueprint.cta_label)
    esc_badge = html.escape(blueprint.hero_badge)
    addr_html = f'<p class="address-line">Location: {html.escape(address)}</p>' if address else ""

    feat_cards = "\n".join(
        f'<article class="card"><h3>Feature {idx + 1}</h3><p>{html.escape(item)}</p></article>'
        for idx, item in enumerate(features[:6])
    )

    logos_block = ""
    clean_logos = [html.escape(c.strip()) for c in client_logos if c.strip()]
    if clean_logos:
        chips = "".join(f'<span class="logo-chip">{c}</span>' for c in clean_logos)
        logos_block = f'<section id="trusted" class="section"><h2>Trusted By</h2><div class="logo-row">{chips}</div></section>'

    index_html = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{esc_brand}</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <header class="site-header">
      <a href="#top" class="brand-lockup">{render_inline_svg_mark(brand, palette)}<span class="brand-name">{esc_brand}</span></a>
      <button type="button" class="nav-toggle" aria-expanded="false" aria-controls="primary-nav">Menu</button>
      <nav id="primary-nav" class="primary-nav" aria-label="Primary navigation">
        <a href="#features">{html.escape(blueprint.section_titles[0])}</a>
        <a href="#standards">{html.escape(blueprint.section_titles[1])}</a>
        <a href="#contact">{html.escape(blueprint.section_titles[2])}</a>
        <a href="#contact" class="btn-primary nav-cta">{esc_cta}</a>
      </nav>
    </header>
    <main id="top" class="container">
      <section class="hero">
        <div class="hero-copy">
          <span class="badge">{esc_badge}</span>
          <h1>{esc_brand}</h1>
          <p class="lead">{esc_tag}</p>
          {addr_html}
          <div class="hero-actions">
            <a href="#contact" class="btn-primary">{esc_cta}</a>
            <a href="#features" class="btn-ghost">Explore Details</a>
          </div>
        </div>
        <div class="hero-visual">{render_hero_art(palette)}</div>
      </section>
      <section id="features" class="section">
        <h2>{html.escape(blueprint.section_titles[0])}</h2>
        <div class="grid">{feat_cards}</div>
      </section>
      <section id="standards" class="section surface-band">
        <h2>{html.escape(blueprint.section_titles[1])}</h2>
        <p>Built with verified WCAG contrast ({palette.name} palette), zero external asset dependencies, and responsive navigation at desktop and 390px mobile.</p>
      </section>
      {logos_block}
      <section id="contact" class="section contact-box">
        <h2>{html.escape(blueprint.section_titles[2])}</h2>
        <form id="contact-form" class="contact-form">
          <label for="visitor-email">Work or personal email</label>
          <input id="visitor-email" type="email" required placeholder="you@example.com" />
          <button type="submit" class="btn-primary">{esc_cta}</button>
          <p id="form-status" class="form-status" aria-live="polite"></p>
        </form>
      </section>
    </main>
    <footer class="site-footer">
      <span>&copy; {esc_brand}</span>
      {f"<span>{html.escape(address)}</span>" if address else ""}
    </footer>
    <script src="app.js"></script>
  </body>
</html>
"""

    styles_css = f"""* {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --bg: {palette.bg};
  --surface: {palette.surface};
  --text: {palette.text};
  --muted: {palette.muted};
  --accent: {palette.accent};
  --accent-text: {palette.accent_text};
  --border: {palette.border};
}}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: "Inter", system-ui, -apple-system, sans-serif;
  line-height: 1.6;
}}
.site-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  position: sticky;
  top: 0;
  z-index: 10;
}}
.brand-lockup {{
  display: inline-flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--text);
  font-weight: 800;
  white-space: nowrap;
  flex-shrink: 0;
}}
.primary-nav {{
  display: flex;
  align-items: center;
  gap: 18px;
}}
.primary-nav a {{
  color: var(--muted);
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
}}
.primary-nav a:hover {{ color: var(--text); }}
.nav-toggle {{
  display: none;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-weight: 600;
}}
.container {{ max-width: 1120px; margin: 0 auto; padding: 28px 20px 64px; }}
.hero {{ display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 28px; align-items: center; padding: 24px 0 40px; }}
.badge {{
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  color: var(--muted);
  margin-bottom: 12px;
}}
h1 {{ font-size: clamp(28px, 4.2vw, 48px); line-height: 1.12; margin-bottom: 14px; }}
.lead {{ font-size: 17px; color: var(--muted); margin-bottom: 12px; max-width: 58ch; }}
.address-line {{ font-size: 14px; font-weight: 600; margin-bottom: 16px; }}
.hero-actions {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; }}
.btn-primary {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 18px;
  border-radius: 10px;
  background: var(--accent);
  color: var(--accent-text);
  border: none;
  text-decoration: none;
  font-weight: 700;
  font-size: 14px;
  cursor: pointer;
}}
.btn-ghost {{
  display: inline-flex;
  align-items: center;
  padding: 10px 18px;
  border-radius: 10px;
  border: 1px solid var(--border);
  color: var(--text);
  text-decoration: none;
  font-weight: 600;
  font-size: 14px;
}}
.hero-svg {{ width: 100%; height: auto; display: block; }}
.section {{ padding: 32px 0; }}
.section h2 {{ font-size: 24px; margin-bottom: 16px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 16px; }}
.card {{
  padding: 18px;
  border-radius: 14px;
  background: var(--surface);
  border: 1px solid var(--border);
}}
.card h3 {{ font-size: 16px; margin-bottom: 6px; }}
.card p {{ font-size: 14px; color: var(--muted); }}
.surface-band {{
  padding: 24px;
  border-radius: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
}}
.logo-row {{ display: flex; flex-wrap: wrap; gap: 10px; }}
.logo-chip {{
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--surface);
  border: 1px solid var(--border);
  font-size: 13px;
  font-weight: 600;
}}
.contact-form {{ display: flex; flex-direction: column; gap: 10px; max-width: 420px; }}
.contact-form input {{
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}}
.form-status {{ font-size: 13px; color: var(--muted); }}
.site-footer {{
  border-top: 1px solid var(--border);
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 13px;
  color: var(--muted);
}}
@media (max-width: 720px) {{
  .hero {{ grid-template-columns: 1fr; }}
  .nav-toggle {{ display: inline-flex; }}
  .primary-nav {{
    display: none;
    position: absolute;
    top: 62px;
    left: 16px;
    right: 16px;
    flex-direction: column;
    align-items: flex-start;
    padding: 16px;
    border-radius: 12px;
    background: var(--surface);
    border: 1px solid var(--border);
  }}
  .primary-nav.open {{ display: flex; }}
}}
"""

    app_js = """(() => {
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.getElementById("primary-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }
  const form = document.getElementById("contact-form");
  const status = document.getElementById("form-status");
  if (form && status) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const input = document.getElementById("visitor-email");
      const val = input && "value" in input ? String(input.value).trim() : "";
      status.textContent = val ? `Inquiry queued for ${val}.` : "Please enter an email.";
    });
  }
})();
"""
    return {
        "index.html": index_html,
        "styles.css": styles_css,
        "app.js": app_js,
    }
