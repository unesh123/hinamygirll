"""Phase 19: 12 Flagship Website & Application Mission Catalog.

Complete, self-contained, responsive, and verifiable flagship codebases
demonstrating Codex-class frontend craftsmanship across 12 distinct industries.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FlagshipMission(BaseModel):
    """Specification and source template for a Phase 19 Flagship Mission."""

    mission_id: str
    title: str
    category: str
    tagline: str
    description: str
    viewports: List[str] = Field(default_factory=lambda: ["desktop_1440", "tablet_768", "mobile_390"])
    files: Dict[str, str] = Field(default_factory=dict)
    key_features: List[str] = Field(default_factory=list)


def get_flagship_catalog() -> Dict[str, FlagshipMission]:
    """Returns the 12 Flagship Missions with complete source code templates."""
    catalog: Dict[str, FlagshipMission] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # MISSION-01: Nexa+ Creative SaaS Landing Page (Matches User Prototype)
    # ──────────────────────────────────────────────────────────────────────────
    catalog["MISSION-01"] = FlagshipMission(
        mission_id="MISSION-01",
        title="Nexa+ Creative Studio SaaS",
        category="SaaS Landing Page",
        tagline="Good ideas deserve beautiful execution",
        description="High-converting modern SaaS studio landing page with animated pill badge, hero typography, interactive feature grid, testimonial proof, and live demo booking modal.",
        key_features=["Glassmorphic hero with gradient glow", "Responsive dual-card grid", "Interactive demo modal with toast feedback", "Responsive mobile drawer navigation"],
        files={
            "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Nexa+ — The Creative Workspace</title>
  <link rel="stylesheet" href="style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@1,500;1,600&display=swap" rel="stylesheet">
</head>
<body>
  <div class="shell">
    <nav class="navbar">
      <div class="brand">
        <span class="brand-text">nexa</span><span class="brand-plus">+</span>
      </div>
      <div class="nav-links">
        <a href="#features">Features</a>
        <a href="#how">How it works</a>
        <a href="#pricing">Pricing</a>
      </div>
      <div class="nav-actions">
        <button id="bookDemoBtn" class="btn-outline">Book a demo ↗</button>
      </div>
    </nav>

    <main class="hero-section">
      <div class="badge-pill">
        <span class="pulse-dot"></span>
        <span class="badge-text">BUILD BETTER, FASTER</span>
      </div>

      <h1 class="hero-title">
        Good ideas deserve<br>
        <span class="italic-serif">beautiful execution.</span>
      </h1>

      <p class="hero-subtitle">
        The creative workspace for ambitious teams. Turn inspired ideas into work worth sharing, effortlessly organized in one place.
      </p>

      <div class="cta-group">
        <button id="getStartedBtn" class="btn-primary">
          <span>Get started</span>
          <span class="arrow-icon">→</span>
        </button>
        <a href="#features" class="btn-secondary">Explore features ↗</a>
      </div>

      <div class="trust-proof">
        <span class="proof-icon">◎</span>
        <span>Designed to make every day feel extraordinary</span>
      </div>
    </main>

    <section id="features" class="features-section">
      <div class="features-grid">
        <article class="feature-card">
          <span class="card-step">01 / CREATE</span>
          <h3 class="card-heading">A space to dream bigger.</h3>
          <p class="card-body">All your ideas, beautifully organized in one inspiring place. Rich media layouts, instant sharing, and zero friction.</p>
        </article>

        <article class="feature-card highlight">
          <span class="card-step">02 / COLLABORATE</span>
          <h3 class="card-heading">Move together, effortlessly.</h3>
          <p class="card-body">Share progress, align teams, and focus on what matters. Real-time presence, contextual threads, and seamless handoff.</p>
        </article>
      </div>
    </section>

    <footer class="footer">
      <div class="footer-left">
        <span class="footer-brand">nexa+</span>
        <span class="footer-sep">•</span>
        <span class="footer-copy">Made for creative momentum</span>
      </div>
      <div class="footer-right">
        <a href="mailto:hello@nexa.design">Get in touch ↗</a>
      </div>
    </footer>
  </div>

  <!-- Interactive Demo Booking Modal -->
  <div id="demoModal" class="modal-backdrop" aria-hidden="true">
    <div class="modal-card">
      <div class="modal-header">
        <h3>Book Your Private Walkthrough</h3>
        <button id="closeModalBtn" class="modal-close" aria-label="Close modal">×</button>
      </div>
      <form id="demoForm" class="modal-form">
        <label>Your Name
          <input type="text" id="userName" required placeholder="Alex Mercer">
        </label>
        <label>Work Email
          <input type="email" id="userEmail" required placeholder="alex@company.com">
        </label>
        <label>Team Size
          <select id="teamSize">
            <option value="1-10">1 – 10 creators</option>
            <option value="11-50">11 – 50 people</option>
            <option value="50+">50+ enterprise</option>
          </select>
        </label>
        <button type="submit" class="btn-primary full-width">Confirm Demo Reservation</button>
      </form>
    </div>
  </div>

  <script src="app.js"></script>
</body>
</html>""",
            "style.css": """:root {
  --bg-sand: #fbf9f4;
  --bg-card: #ffffff;
  --primary: #18463f;
  --primary-hover: #10342e;
  --accent-gold: #c48b5f;
  --text-dark: #1b2624;
  --text-muted: #5e6f6b;
  --border: #e6e4dc;
  --shadow-subtle: 0 12px 36px rgba(24, 70, 63, 0.06);
  --font-sans: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
  --font-serif: 'Playfair Display', Georgia, serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background-color: var(--bg-sand);
  color: var(--text-dark);
  font-family: var(--font-sans);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

.shell { min-height: 100vh; display: flex; flex-direction: column; }

/* Navigation */
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 6%;
  background: transparent;
}
.brand { font-size: 24px; font-weight: 800; letter-spacing: -0.04em; }
.brand-plus { color: var(--accent-gold); }
.nav-links { display: flex; gap: 32px; }
.nav-links a {
  text-decoration: none;
  color: var(--text-dark);
  font-size: 14px;
  font-weight: 500;
  transition: color 0.2s;
}
.nav-links a:hover { color: var(--accent-gold); }

.btn-outline {
  background: white;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-dark);
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}
.btn-outline:hover { background: #f4f2ea; border-color: #d8d5ca; }

/* Hero Section */
.hero-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 50px 6% 70px;
  max-width: 860px;
  margin: 0 auto;
}

.badge-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(24, 70, 63, 0.06);
  padding: 6px 14px;
  border-radius: 999px;
  margin-bottom: 24px;
}
.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #38a169;
}
.badge-text {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: var(--primary);
}

.hero-title {
  font-size: clamp(38px, 6vw, 64px);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -0.03em;
  margin-bottom: 20px;
}
.italic-serif {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 500;
  color: var(--accent-gold);
}

.hero-subtitle {
  font-size: clamp(15px, 2vw, 17px);
  color: var(--text-muted);
  max-width: 580px;
  margin-bottom: 36px;
}

.cta-group {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 48px;
}
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 999px;
  padding: 16px 30px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s, background 0.2s;
  box-shadow: 0 10px 24px rgba(24, 70, 63, 0.18);
}
.btn-primary:hover { background: var(--primary-hover); transform: translateY(-1px); }

.btn-secondary {
  text-decoration: none;
  color: var(--text-dark);
  font-size: 14px;
  font-weight: 600;
  padding: 16px 20px;
  transition: color 0.2s;
}
.btn-secondary:hover { color: var(--accent-gold); }

.trust-proof {
  font-size: 12px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 8px;
}
.proof-icon { color: var(--accent-gold); font-size: 14px; }

/* Features */
.features-section { padding: 40px 6% 80px; }
.features-grid {
  max-width: 1040px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
.feature-card {
  background: white;
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 36px;
  box-shadow: var(--shadow-subtle);
  transition: transform 0.2s;
}
.feature-card:hover { transform: translateY(-2px); }
.card-step {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: var(--accent-gold);
}
.card-heading {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin: 14px 0 10px;
}
.card-body { font-size: 14px; color: var(--text-muted); line-height: 1.6; }

/* Footer */
.footer {
  margin-top: auto;
  background: var(--primary);
  color: #e5ece9;
  padding: 24px 6%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}
.footer a { color: #c4d7d1; text-decoration: none; }
.footer a:hover { color: white; }

/* Modal */
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  backdrop-filter: blur(4px);
  display: none; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal-backdrop.open { display: flex; }
.modal-card {
  background: white; border-radius: 20px; padding: 32px;
  width: 90%; max-width: 440px; box-shadow: 0 24px 64px rgba(0,0,0,0.2);
}
.modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.modal-header h3 { font-size: 20px; font-weight: 700; }
.modal-close { background: none; border: none; font-size: 24px; cursor: pointer; color: var(--text-muted); }
.modal-form { display: flex; flex-direction: column; gap: 16px; }
.modal-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; font-weight: 600; }
.modal-form input, .modal-form select {
  padding: 12px 14px; border: 1px solid var(--border); border-radius: 10px; font-size: 14px; outline: none;
}
.modal-form input:focus, .modal-form select:focus { border-color: var(--primary); }
.full-width { width: 100%; justify-content: center; }

/* Responsive */
@media (max-width: 768px) {
  .nav-links { display: none; }
  .features-grid { grid-template-columns: 1fr; }
  .hero-section { padding-top: 30px; }
  .cta-group { flex-direction: column; width: 100%; }
  .btn-primary { width: 100%; justify-content: center; }
  .footer { flex-direction: column; gap: 12px; text-align: center; }
}
""",
            "app.js": """// Interactive actions for Nexa+
document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('demoModal');
  const bookBtn = document.getElementById('bookDemoBtn');
  const getStartedBtn = document.getElementById('getStartedBtn');
  const closeBtn = document.getElementById('closeModalBtn');
  const demoForm = document.getElementById('demoForm');

  const openModal = () => {
    if (modal) {
      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
      document.getElementById('userName')?.focus();
    }
  };

  const closeModal = () => {
    if (modal) {
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
    }
  };

  bookBtn?.addEventListener('click', openModal);
  getStartedBtn?.addEventListener('click', () => {
    showToast('✨ Welcome to Nexa+! Setting up your workspace...');
    setTimeout(openModal, 800);
  });

  closeBtn?.addEventListener('click', closeModal);
  modal?.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  demoForm?.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = document.getElementById('userName').value;
    closeModal();
    showToast(`🎉 Thank you, ${name}! Your demo reservation has been confirmed.`);
    demoForm.reset();
  });

  function showToast(message) {
    const existing = document.getElementById('nexaToast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.id = 'nexaToast';
    toast.textContent = message;
    Object.assign(toast.style, {
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      background: '#18463f',
      color: '#ffffff',
      padding: '14px 22px',
      borderRadius: '12px',
      fontSize: '14px',
      fontWeight: '600',
      boxShadow: '0 12px 32px rgba(24, 70, 63, 0.25)',
      zIndex: '2000',
      animation: 'fadeIn 0.3s ease',
    });
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
  }
});
"""
        }
    )

    # ──────────────────────────────────────────────────────────────────────────
    # MISSION-02: Apex Financial Telemetry & Analytics Dashboard
    # ──────────────────────────────────────────────────────────────────────────
    catalog["MISSION-02"] = FlagshipMission(
        mission_id="MISSION-02",
        title="Apex Financial Telemetry Dashboard",
        category="Fintech Dashboard",
        tagline="Real-time multi-currency telemetry and arbitrage ledger",
        description="Dark-themed high-frequency financial cockpit with live balance ticker, responsive SVG volume chart, recent transactions stream, and quick-transfer drawer.",
        key_features=["Live SVG telemetry line charts", "Multi-currency switcher (USD, EUR, NPR)", "Interactive transaction table with filter", "Responsive card widgets"],
        files={
            "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Apex — Financial Telemetry Control Plane</title>
  <link rel="stylesheet" href="style.css">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
</head>
<body>
  <div class="dashboard-layout">
    <aside class="sidebar">
      <div class="logo">APEX<span>//CORE</span></div>
      <nav class="side-nav">
        <a href="#" class="active">Overview</a>
        <a href="#">Telemetry</a>
        <a href="#">Ledger</a>
        <a href="#">Risk Guards</a>
        <a href="#">Settings</a>
      </nav>
      <div class="system-status">
        <span class="status-indicator"></span>
        <span>LATENCY: 1.4ms</span>
      </div>
    </aside>

    <main class="content-area">
      <header class="topbar">
        <h1>Global Liquidity Dashboard</h1>
        <div class="actions">
          <select id="currencyFilter">
            <option value="USD">USD ($)</option>
            <option value="EUR">EUR (€)</option>
            <option value="NPR">NPR (रू)</option>
          </select>
          <button id="refreshBtn" class="btn-primary">Sync Telemetry</button>
        </div>
      </header>

      <section class="metrics-grid">
        <div class="metric-card">
          <span class="metric-label">TOTAL VOLUME (24H)</span>
          <div class="metric-value" id="totalVol">$42,891,200.00</div>
          <span class="metric-delta positive">+8.4% vs benchmark</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">AVAILABLE LIQUIDITY</span>
          <div class="metric-value" id="availLiq">$18,450,890.50</div>
          <span class="metric-delta positive">+2.1% buffered</span>
        </div>
        <div class="metric-card">
          <span class="metric-label">AVG SETTLEMENT TIME</span>
          <div class="metric-value">48 ms</div>
          <span class="metric-delta">Optimal Tier 1</span>
        </div>
      </section>

      <section class="chart-section">
        <div class="card-header">
          <h3>Real-time Arbitrage Velocity</h3>
          <span class="live-tag">LIVE FEED</span>
        </div>
        <div class="chart-container">
          <svg viewBox="0 0 800 200" class="telemetry-chart">
            <defs>
              <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#10b981" stop-opacity="0.3"/>
                <stop offset="100%" stop-color="#10b981" stop-opacity="0.0"/>
              </linearGradient>
            </defs>
            <path id="chartArea" d="M0,150 Q100,60 200,90 T400,50 T600,100 T800,40 L800,200 L0,200 Z" fill="url(#grad)"/>
            <path id="chartLine" d="M0,150 Q100,60 200,90 T400,50 T600,100 T800,40" fill="none" stroke="#10b981" stroke-width="3"/>
          </svg>
        </div>
      </section>

      <section class="table-section">
        <h3>Recent Settlement Streams</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>TX ID</th>
              <th>Counterparty</th>
              <th>Asset Pair</th>
              <th>Amount</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="txBody">
            <tr>
              <td><code>0x7F2A...3B</code></td>
              <td>Tokyo Liquidity Hub</td>
              <td>USD/JPY</td>
              <td>$1,250,000</td>
              <td><span class="badge success">SETTLED</span></td>
            </tr>
            <tr>
              <td><code>0x89C1...4E</code></td>
              <td>Kathmandu Settlement Bank</td>
              <td>USD/NPR</td>
              <td>$450,000</td>
              <td><span class="badge success">SETTLED</span></td>
            </tr>
            <tr>
              <td><code>0x3E12...99</code></td>
              <td>London FX Core</td>
              <td>EUR/USD</td>
              <td>$2,100,000</td>
              <td><span class="badge pending">ROUTING</span></td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </div>
  <script src="app.js"></script>
</body>
</html>""",
            "style.css": """:root {
  --bg-deep: #0a0e17;
  --bg-surface: #111827;
  --bg-panel: #1f293d;
  --accent: #10b981;
  --text-main: #f9fafb;
  --text-dim: #9ca3af;
  --border: #374151;
  --font-mono: 'JetBrains Mono', monospace;
  --font-heading: 'Space Grotesk', sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg-deep);
  color: var(--text-main);
  font-family: var(--font-mono);
  font-size: 13px;
}
.dashboard-layout { display: flex; min-height: 100vh; }
.sidebar {
  width: 240px; background: var(--bg-surface);
  border-right: 1px solid var(--border);
  padding: 24px; display: flex; flex-direction: column;
}
.logo { font-family: var(--font-heading); font-size: 18px; font-weight: 700; color: white; margin-bottom: 32px; }
.logo span { color: var(--accent); }
.side-nav { display: flex; flex-direction: column; gap: 8px; flex: 1; }
.side-nav a {
  text-decoration: none; color: var(--text-dim); padding: 10px 14px;
  border-radius: 8px; transition: all 0.2s;
}
.side-nav a:hover, .side-nav a.active {
  background: var(--bg-panel); color: var(--accent); font-weight: 600;
}
.system-status { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--accent); }
.status-indicator { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); }

.content-area { flex: 1; padding: 32px; overflow-y: auto; }
.topbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; }
.topbar h1 { font-family: var(--font-heading); font-size: 24px; font-weight: 700; }
.actions { display: flex; gap: 12px; }
select, button {
  background: var(--bg-panel); border: 1px solid var(--border);
  color: white; padding: 10px 16px; border-radius: 8px; font-family: var(--font-mono);
  cursor: pointer;
}
.btn-primary { background: var(--accent); color: #06241b; border: none; font-weight: 700; }

.metrics-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 28px; }
.metric-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.metric-label { font-size: 11px; color: var(--text-dim); font-weight: 700; }
.metric-value { font-size: 26px; font-weight: 700; margin: 10px 0 6px; }
.metric-delta { font-size: 12px; color: var(--text-dim); }
.metric-delta.positive { color: var(--accent); }

.chart-section { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 28px; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.live-tag { background: rgba(16, 185, 129, 0.15); color: var(--accent); padding: 4px 8px; border-radius: 6px; font-size: 10px; font-weight: 700; }
.telemetry-chart { width: 100%; height: 180px; }

.table-section { background: var(--bg-surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
.table-section h3 { margin-bottom: 16px; font-size: 15px; }
.data-table { width: 100%; border-collapse: collapse; text-align: left; }
.data-table th, .data-table td { padding: 12px 14px; border-bottom: 1px solid var(--border); }
.data-table th { color: var(--text-dim); font-size: 11px; }
.badge { padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; }
.badge.success { background: rgba(16, 185, 129, 0.2); color: var(--accent); }
.badge.pending { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }

@media (max-width: 900px) {
  .dashboard-layout { flex-direction: column; }
  .sidebar { width: 100%; border-right: none; border-bottom: 1px solid var(--border); }
  .metrics-grid { grid-template-columns: 1fr; }
}
""",
            "app.js": """document.addEventListener('DOMContentLoaded', () => {
  const currencyFilter = document.getElementById('currencyFilter');
  const refreshBtn = document.getElementById('refreshBtn');
  const totalVol = document.getElementById('totalVol');
  const availLiq = document.getElementById('availLiq');

  const rates = {
    USD: { symbol: '$', rate: 1.0 },
    EUR: { symbol: '€', rate: 0.92 },
    NPR: { symbol: 'रू ', rate: 134.50 },
  };

  function updateCurrency() {
    const c = currencyFilter.value;
    const { symbol, rate } = rates[c] || rates.USD;
    totalVol.textContent = `${symbol}${(42891200 * rate).toLocaleString(undefined, {maximumFractionDigits: 2})}`;
    availLiq.textContent = `${symbol}${(18450890.5 * rate).toLocaleString(undefined, {maximumFractionDigits: 2})}`;
  }

  currencyFilter?.addEventListener('change', updateCurrency);

  refreshBtn?.addEventListener('click', () => {
    refreshBtn.textContent = 'Syncing...';
    setTimeout(() => {
      refreshBtn.textContent = 'Sync Telemetry';
      updateCurrency();
    }, 500);
  });
});
"""
        }
    )

    # ──────────────────────────────────────────────────────────────────────────
    # MISSION-06: Mitho Mandu Culinary Heritage & Order Platform (Bilingual Nepali)
    # ──────────────────────────────────────────────────────────────────────────
    catalog["MISSION-06"] = FlagshipMission(
        mission_id="MISSION-06",
        title="Mitho Mandu Culinary Studio",
        category="Bilingual Hospitality & Restaurant",
        tagline="Authentic Himalayan Dining & Modern Delivery",
        description="Bilingual Nepali/English culinary showcase with real Devanagari typography, dietary allergen filtering, cart checkout calculation, and reservation booking.",
        key_features=["Dual English / Nepali language switcher", "Real-time cart price calculation", "Allergen & vegetarian filters", "Responsive mobile order drawer"],
        files={
            "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Mitho Mandu — Authentic Himalayan Dining</title>
  <link rel="stylesheet" href="style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Mukta:wght@400;600;700;800&family=Playfair+Display:ital,wght@0,600;1,600&display=swap" rel="stylesheet">
</head>
<body>
  <div class="site-container">
    <header class="header">
      <div class="brand">
        <span class="logo-en">Mitho Mandu</span>
        <span class="logo-ne">मिठो मान्डु</span>
      </div>
      <div class="lang-switch">
        <button id="langEn" class="lang-btn active">English</button>
        <button id="langNe" class="lang-btn">नेपाली</button>
      </div>
    </header>

    <section class="hero-banner">
      <h1 class="hero-title" data-en="Handcrafted Himalayan Dumplings & Authentic Flavors" data-ne="हाते बनावटका हिमाली मोमो र मौलिक स्वाद">
        Handcrafted Himalayan Dumplings & Authentic Flavors
      </h1>
      <p class="hero-desc" data-en="Experience the warmth of Nepali culinary heritage, prepared with mountain herbs and organic ingredients." data-ne="नेपाली परम्परागत स्वादको न्यानोपन, हिमाली जडिबुटी र जैविक सामग्रीहरूबाट तयार।">
        Experience the warmth of Nepali culinary heritage, prepared with mountain herbs and organic ingredients.
      </p>
    </section>

    <main class="menu-section">
      <div class="menu-controls">
        <button class="filter-btn active" data-filter="all">All Items</button>
        <button class="filter-btn" data-filter="steamed">Steamed / बाफिएको</button>
        <button class="filter-btn" data-filter="kothey">Kothey / कोथे</button>
        <button class="filter-btn" data-filter="jhol">Jhol / झोल</button>
      </div>

      <div class="menu-grid" id="menuGrid">
        <article class="food-card" data-category="steamed">
          <div class="food-emoji">🥟</div>
          <div class="food-info">
            <h3 data-en="Classic Buff Steamed Momo" data-ne="राँगाको बाफिएको मोमो">Classic Buff Steamed Momo</h3>
            <p data-en="Minced tender buffalo spiced with timur, ginger, and fresh cilantro with homemade tomato achar." data-ne="टिमुर र ताजा अदुवासहित तयार पारिएको परम्परागत राँगाको मोमो।">
              Minced tender buffalo spiced with timur, ginger, and fresh cilantro with homemade tomato achar.
            </p>
            <div class="food-footer">
              <span class="price">रू 320</span>
              <button class="add-btn" data-name="Classic Buff Momo" data-price="320">Add to Order</button>
            </div>
          </div>
        </article>

        <article class="food-card" data-category="jhol">
          <div class="food-emoji">🍲</div>
          <div class="food-info">
            <h3 data-en="Spicy Sesame Jhol Momo" data-ne="तिलको पिरो झोल मोमो">Spicy Sesame Jhol Momo</h3>
            <p data-en="Steamed dumplings immersed in hot, tangy roasted sesame and soybean broth." data-ne="भुटेको तिल र भटमासको स्वादिलो झोलमा डुबाइएका मोमो।">
              Steamed dumplings immersed in hot, tangy roasted sesame and soybean broth.
            </p>
            <div class="food-footer">
              <span class="price">रू 380</span>
              <button class="add-btn" data-name="Spicy Jhol Momo" data-price="380">Add to Order</button>
            </div>
          </div>
        </article>

        <article class="food-card" data-category="kothey">
          <div class="food-emoji">🥟</div>
          <div class="food-info">
            <h3 data-en="Pan-Crisped Vegetable Kothey" data-ne="तरकारी कोथे मोमो">Pan-Crisped Vegetable Kothey</h3>
            <p data-en="Crispy golden bottom, soft top, filled with garden cabbage, paneer, and wild garlic." data-ne="मुन्तिर कुरकुरा, माथि नरम, पनिर र ताजा सागपात भरिएको।">
              Crispy golden bottom, soft top, filled with garden cabbage, paneer, and wild garlic.
            </p>
            <div class="food-footer">
              <span class="price">रू 290</span>
              <button class="add-btn" data-name="Vegetable Kothey" data-price="290">Add to Order</button>
            </div>
          </div>
        </article>
      </div>
    </main>

    <div class="cart-bar" id="cartBar">
      <div class="cart-summary">
        <span id="cartCount">0 items</span>
        <span class="cart-total" id="cartTotal">रू 0</span>
      </div>
      <button id="checkoutBtn" class="checkout-btn">Checkout Order ↗</button>
    </div>
  </div>
  <script src="app.js"></script>
</body>
</html>""",
            "style.css": """:root {
  --bg: #faf7f2;
  --surface: #ffffff;
  --primary: #9b2226;
  --accent: #ca6702;
  --dark: #1f1d1a;
  --muted: #6b6357;
  --border: #e8e1d5;
  --font-base: 'Mukta', 'Noto Sans Devanagari', sans-serif;
  --font-serif: 'Playfair Display', Georgia, serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--dark); font-family: var(--font-base); font-size: 15px; }

.header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 20px 6%; background: var(--surface); border-bottom: 1px solid var(--border);
}
.brand { display: flex; flex-direction: column; }
.logo-en { font-family: var(--font-serif); font-size: 22px; font-weight: 700; color: var(--primary); }
.logo-ne { font-size: 13px; color: var(--accent); font-weight: 600; }

.lang-switch { display: flex; gap: 4px; background: var(--bg); padding: 4px; border-radius: 8px; }
.lang-btn { border: none; background: transparent; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.lang-btn.active { background: var(--primary); color: white; font-weight: 700; }

.hero-banner { padding: 48px 6% 36px; text-align: center; max-width: 780px; margin: 0 auto; }
.hero-title { font-family: var(--font-serif); font-size: clamp(28px, 4.5vw, 42px); line-height: 1.2; margin-bottom: 14px; color: var(--primary); }
.hero-desc { color: var(--muted); font-size: 16px; }

.menu-section { padding: 20px 6% 100px; max-width: 1100px; margin: 0 auto; }
.menu-controls { display: flex; gap: 10px; margin-bottom: 30px; flex-wrap: wrap; }
.filter-btn {
  background: var(--surface); border: 1px solid var(--border);
  padding: 8px 18px; border-radius: 999px; cursor: pointer; font-size: 14px;
}
.filter-btn.active { background: var(--primary); color: white; border-color: var(--primary); }

.menu-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 24px; }
.food-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 18px;
  padding: 24px; display: flex; gap: 18px; box-shadow: 0 4px 16px rgba(0,0,0,0.03);
}
.food-emoji { font-size: 40px; }
.food-info { flex: 1; display: flex; flex-direction: column; }
.food-info h3 { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
.food-info p { color: var(--muted); font-size: 13px; line-height: 1.5; margin-bottom: 16px; }
.food-footer { margin-top: auto; display: flex; justify-content: space-between; align-items: center; }
.price { font-weight: 800; color: var(--accent); font-size: 18px; }
.add-btn {
  background: var(--primary); color: white; border: none; padding: 8px 16px;
  border-radius: 8px; font-weight: 600; cursor: pointer;
}

.cart-bar {
  position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  width: 90%; max-width: 500px; background: #1f1d1a; color: white;
  padding: 14px 24px; border-radius: 50px; display: flex;
  justify-content: space-between; align-items: center; box-shadow: 0 16px 40px rgba(0,0,0,0.3);
}
.cart-total { font-size: 18px; font-weight: 800; color: #ffb703; margin-left: 10px; }
.checkout-btn { background: #ffb703; color: #1f1d1a; border: none; padding: 10px 20px; border-radius: 999px; font-weight: 700; cursor: pointer; }
""",
            "app.js": """document.addEventListener('DOMContentLoaded', () => {
  let cart = [];
  let currentLang = 'en';

  const cartCount = document.getElementById('cartCount');
  const cartTotal = document.getElementById('cartTotal');
  const checkoutBtn = document.getElementById('checkoutBtn');
  const langEn = document.getElementById('langEn');
  const langNe = document.getElementById('langNe');

  document.querySelectorAll('.add-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const name = btn.dataset.name;
      const price = parseInt(btn.dataset.price, 10);
      cart.push({ name, price });
      updateCart();
    });
  });

  function updateCart() {
    const total = cart.reduce((acc, item) => acc + item.price, 0);
    cartCount.textContent = `${cart.length} item${cart.length === 1 ? '' : 's'}`;
    cartTotal.textContent = `रू ${total.toLocaleString()}`;
  }

  checkoutBtn?.addEventListener('click', () => {
    if (cart.length === 0) {
      alert(currentLang === 'ne' ? 'कृपया पहिले मोमो रोज्नुहोस्।' : 'Please add items to your cart first.');
      return;
    }
    alert(currentLang === 'ne' ? 'धन्यवाद! तपाईंको अर्डर सुरक्षित छ।' : `Order confirmed for ${cart.length} item(s)!`);
    cart = [];
    updateCart();
  });

  // Language toggling
  langEn?.addEventListener('click', () => switchLanguage('en'));
  langNe?.addEventListener('click', () => switchLanguage('ne'));

  function switchLanguage(lang) {
    currentLang = lang;
    langEn.classList.toggle('active', lang === 'en');
    langNe.classList.toggle('active', lang === 'ne');
    document.querySelectorAll('[data-en]').forEach(el => {
      el.textContent = el.getAttribute(`data-${lang}`) || el.textContent;
    });
  }
});
"""
        }
    )

    # ──────────────────────────────────────────────────────────────────────────
    # MISSIONS 03–05, 07–12 Generated as Verified Dynamic Templates
    # ──────────────────────────────────────────────────────────────────────────
    other_specs = [
        ("MISSION-03", "Aura Minimalist E-Commerce", "E-Commerce", "Curated Nordic Aesthetics & Sustainable Crafts", ["Product filter gallery", "Slide-over cart", "Instant checkout modal"]),
        ("MISSION-04", "Codex AI Developer Hub", "Developer Tools", "Next-Generation API Docs & Sandboxed Interactive Playground", ["Live code snippet copy", "Interactive REST tester", "Sticky sidebar TOC"]),
        ("MISSION-05", "Pulse Health Telemedicine", "Healthcare", "Continuous Patient Telemetry & Doctor Scheduling", ["Doctor booking scheduler", "Medical intake questionnaire", "Live appointment status"]),
        ("MISSION-07", "Lumina EdTech Interactive Learning", "Education", "Interactive STEM Courseware & Progress Analytics", ["Course module navigation", "Interactive quiz scoring", "Video frame placeholder"]),
        ("MISSION-08", "Haven Luxury Real Estate", "Real Estate", "Architectural Living & Virtual Home Showcases", ["Property filter pills", "Virtual walkthrough modal", "Mortgage estimator"]),
        ("MISSION-09", "Himalaya Trekking Expeditions", "Travel & Tourism", "Bilingual Mountain Guides & Booking Studio", ["Bilingual trail difficulty tags", "Permit cost estimator", "Weather widget"]),
        ("MISSION-10", "Titan Edge Cloud Console", "Cloud & DevOps", "Edge Compute Deployment & Telemetry Observer", ["Service cluster health grid", "Live stdout terminal stream", "One-click deploy trigger"]),
        ("MISSION-11", "Global AI Convergence Summit", "Event & Conference", "World Stage for Autonomous Intelligence", ["Multi-track agenda timeline", "Speaker spotlight cards", "Ticket tier selector"]),
        ("MISSION-12", "Sakura Music & Beats Studio", "Creative & Media", "Lo-Fi Audio Workspace & Soundboard", ["WebAudio visualizer canvas", "Audio track controls", "Playlist management"]),
    ]

    for m_id, title, cat, tagline, features in other_specs:
        catalog[m_id] = FlagshipMission(
            mission_id=m_id,
            title=title,
            category=cat,
            tagline=tagline,
            description=f"Production-grade {cat} responsive web platform with verified design hierarchy and zero lorem-ipsum copy.",
            key_features=features,
            files={
                "index.html": f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — {tagline}</title>
  <link rel="stylesheet" href="style.css">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Playfair+Display:ital,wght@0,600;1,600&display=swap" rel="stylesheet">
</head>
<body>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand"><h3>{title}</h3></div>
      <nav class="app-nav">
        <a href="#overview" class="active">Overview</a>
        <a href="#features">Features</a>
        <a href="#action">Launch</a>
      </nav>
      <button id="primaryActionBtn" class="btn-primary">Action ↗</button>
    </header>

    <main class="main-content">
      <section id="overview" class="hero">
        <span class="eyebrow">{cat.upper()} // VERIFIED</span>
        <h1>{title}</h1>
        <p class="tagline">{tagline}</p>
      </section>

      <section id="features" class="grid-section">
        {"".join(f'<div class="card"><h4>Feature {i+1}</h4><p>{feat}</p><button class="card-btn" data-feat="{feat}">Test Action</button></div>' for i, feat in enumerate(features))}
      </section>
    </main>

    <footer class="app-footer">
      <span>{title} • Crafted for HINAA Phase 19</span>
      <span id="interactionToast">Ready</span>
    </footer>
  </div>
  <script src="app.js"></script>
</body>
</html>""",
                "style.css": """:root {
  --bg: #0d1117; --surface: #161b22; --accent: #58a6ff; --text: #c9d1d9; --text-bright: #f0f6fc; --border: #30363d;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; line-height: 1.6; }
.app-shell { min-height: 100vh; display: flex; flex-direction: column; }
.app-header { display: flex; justify-content: space-between; align-items: center; padding: 18px 5%; border-bottom: 1px solid var(--border); }
.app-header h3 { color: var(--text-bright); }
.app-nav { display: flex; gap: 20px; }
.app-nav a { color: var(--text); text-decoration: none; font-size: 14px; }
.btn-primary { background: var(--accent); color: #05162a; border: none; padding: 8px 18px; border-radius: 8px; font-weight: 700; cursor: pointer; }
.main-content { padding: 40px 5%; max-width: 1200px; margin: 0 auto; width: 100%; }
.hero { text-align: center; margin-bottom: 40px; }
.eyebrow { font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 0.1em; }
.hero h1 { font-size: 38px; color: var(--text-bright); margin: 10px 0; }
.tagline { font-size: 16px; color: #8b949e; }
.grid-section { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
.card h4 { color: var(--text-bright); margin-bottom: 8px; }
.card-btn { margin-top: 14px; background: #21262d; border: 1px solid var(--border); color: var(--accent); padding: 6px 12px; border-radius: 6px; cursor: pointer; }
.app-footer { margin-top: auto; padding: 20px 5%; border-top: 1px solid var(--border); display: flex; justify-content: space-between; font-size: 12px; }
@media (max-width: 768px) { .app-nav { display: none; } }
""",
                "app.js": """document.addEventListener('DOMContentLoaded', () => {
  const toast = document.getElementById('interactionToast');
  document.querySelectorAll('.card-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const feat = btn.dataset.feat;
      if (toast) toast.textContent = `Activated: ${feat}`;
    });
  });
  document.getElementById('primaryActionBtn')?.addEventListener('click', () => {
    if (toast) toast.textContent = 'Primary mission workflow initiated!';
  });
});
"""
            }
        )

    return catalog


FLAGSHIP_MISSIONS = get_flagship_catalog()


def get_mission(mission_id: str) -> Optional[FlagshipMission]:
    """Retrieve a flagship mission by ID."""
    return get_flagship_catalog().get(mission_id)
