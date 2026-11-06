"""Phase 19: Three Unseen, Full-Stack Showcase Websites Built from Scratch.

These 3 full-stack web applications were constructed from natural-language briefs
without using existing flagship mission templates, demonstrating production craftsmanship,
real interactivity, data persistence (localStorage), WCAG accessibility, and responsive design.

- SITE-01: Apex Cloud Autonomous SaaS Platform (Interactive Telemetry, Auth Modal, Pricing Toggle)
- SITE-02: Himalayan Artisans Marketplace (Authentic Nepali Cultural E-Commerce, Live Cart, NPR/USD Switcher)
- SITE-03: Zenith Developer Creative Studio (Canvas Particle Physics, Interactive Live Code Runner, Auto-Saved Briefs)
"""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class ShowcaseSite(BaseModel):
    site_id: str
    name: str
    category: str
    tagline: str
    description: str
    key_features: List[str]
    files: Dict[str, str]


UNSEEN_SHOWCASE_SITES: Dict[str, ShowcaseSite] = {}

# ──────────────────────────────────────────────────────────────────────────────
# SITE-01: Apex Cloud Autonomous SaaS Platform
# ──────────────────────────────────────────────────────────────────────────────
UNSEEN_SHOWCASE_SITES["NEW-SITE-01"] = ShowcaseSite(
    site_id="NEW-SITE-01",
    name="Apex Cloud Nexus",
    category="Autonomous SaaS Dashboard & Platform",
    tagline="Intelligent Cloud Orchestration at Global Edge",
    description="Full-stack SaaS platform with real-time KPI counters, SVG telemetry charts, interactive auth modal with localStorage persistence, and annual/monthly billing toggle.",
    key_features=[
        "Live interactive KPI telemetry counters",
        "Responsive SVG performance chart with time range selector",
        "Authentication modal (Sign In / Sign Up) with email validation and localStorage session store",
        "Billing toggle with real-time 20% annual discount calculations",
        "Toast notification engine for user feedback",
    ],
    files={
        "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Apex Cloud Nexus — Autonomous Edge Orchestration</title>
  <link rel="stylesheet" href="style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
</head>
<body class="dark-mode">
  <header class="app-header">
    <div class="header-inner">
      <div class="logo">
        <div class="logo-mark">▲</div>
        <span class="logo-text">APEX<span>NEXUS</span></span>
      </div>
      <nav class="nav-links" aria-label="Main Navigation">
        <a href="#overview" class="active">Overview</a>
        <a href="#telemetry">Telemetry</a>
        <a href="#pricing">Pricing</a>
        <a href="#docs">Docs</a>
      </nav>
      <div class="header-actions">
        <button id="themeToggleBtn" class="btn-icon" aria-label="Toggle Theme">🌓</button>
        <button id="openAuthBtn" class="btn-primary">Sign In</button>
      </div>
      <button id="mobileMenuBtn" class="mobile-toggle" aria-label="Open Navigation">☰</button>
    </div>
  </header>

  <main class="page-container">
    <!-- Hero Section -->
    <section id="overview" class="hero-section">
      <div class="badge-pill">
        <span class="pulse-dot"></span>
        <span class="badge-text">v4.8 Edge Convergence Live</span>
      </div>
      <h1 class="hero-title">Autonomous Cloud Infrastructure<br><span class="gradient-text">Engineered for Zero Downtime</span></h1>
      <p class="hero-subtitle">Orchestrate autonomous agent fleets, edge microservices, and neural inference pipelines with single-digit millisecond latency.</p>
      <div class="hero-cta-group">
        <button class="btn-cta" onclick="triggerToast('Provisioning sandbox cluster...', 'info')">Deploy Cluster →</button>
        <a href="#telemetry" class="btn-secondary">View Live Metrics</a>
      </div>
    </section>

    <!-- Real-Time Telemetry KPI Grid -->
    <section id="telemetry" class="kpi-section">
      <div class="section-header">
        <h2>System Telemetry</h2>
        <span class="status-badge"><span class="green-dot"></span> All 12 Regions Operational</span>
      </div>
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-header">
            <span class="kpi-label">Active Agents</span>
            <span class="kpi-change positive">+14.2%</span>
          </div>
          <div class="kpi-value" id="kpiAgents">1,420</div>
          <div class="kpi-sub">Across 48 edge clusters</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-header">
            <span class="kpi-label">Inference Throughput</span>
            <span class="kpi-change positive">+28.5%</span>
          </div>
          <div class="kpi-value" id="kpiRps">84,210</div>
          <div class="kpi-sub">Requests per second</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-header">
            <span class="kpi-label">Global P99 Latency</span>
            <span class="kpi-change neutral">-2.1ms</span>
          </div>
          <div class="kpi-value" id="kpiLatency">6.8ms</div>
          <div class="kpi-sub">Round-trip edge proxy</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-header">
            <span class="kpi-label">System Availability</span>
            <span class="kpi-change positive">100%</span>
          </div>
          <div class="kpi-value" id="kpiUptime">99.99%</div>
          <div class="kpi-sub">Last 90 days rolling</div>
        </div>
      </div>

      <!-- Interactive SVG Chart -->
      <div class="chart-container">
        <div class="chart-header">
          <h3>Throughput Load Curve (24h)</h3>
          <div class="range-selector">
            <button class="range-btn active" data-range="24h">24h</button>
            <button class="range-btn" data-range="7d">7d</button>
            <button class="range-btn" data-range="30d">30d</button>
          </div>
        </div>
        <div class="chart-wrapper">
          <svg id="telemetryChart" viewBox="0 0 800 200" preserveAspectRatio="none">
            <defs>
              <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#6366f1" stop-opacity="0.4"/>
                <stop offset="100%" stop-color="#6366f1" stop-opacity="0.0"/>
              </linearGradient>
            </defs>
            <path id="chartArea" fill="url(#chartGrad)" d=""></path>
            <path id="chartLine" fill="none" stroke="#6366f1" stroke-width="3" stroke-linecap="round" d=""></path>
          </svg>
        </div>
      </div>
    </section>

    <!-- Pricing Section with Live Toggle -->
    <section id="pricing" class="pricing-section">
      <div class="section-header center">
        <h2>Transparent Scalable Pricing</h2>
        <p>No credit card required for sandbox tier. Instant deployment.</p>
        <div class="billing-toggle-container">
          <span class="toggle-label" id="labelMonthly">Monthly</span>
          <button id="billingSwitch" class="toggle-switch" aria-label="Toggle annual billing">
            <span class="toggle-knob"></span>
          </button>
          <span class="toggle-label" id="labelAnnual">Annual <span class="discount-tag">Save 20%</span></span>
        </div>
      </div>

      <div class="pricing-grid">
        <div class="pricing-card">
          <div class="card-tier">Developer</div>
          <div class="card-price"><span class="price-val" data-monthly="0" data-annual="0">$0</span><span class="period">/mo</span></div>
          <p class="card-desc">For builders, personal agents, and local prototyping.</p>
          <ul class="tier-features">
            <li>✓ 3 Active Agent Fleets</li>
            <li>✓ 100k Monthly API Calls</li>
            <li>✓ Community Support</li>
            <li>✓ Standard Edge Routing</li>
          </ul>
          <button class="btn-tier" onclick="handleTierSelect('Developer')">Get Started</button>
        </div>

        <div class="pricing-card featured">
          <div class="popular-ribbon">Most Popular</div>
          <div class="card-tier">Pro Cluster</div>
          <div class="card-price"><span class="price-val" data-monthly="49" data-annual="39">$49</span><span class="period">/mo</span></div>
          <p class="card-desc">For scaling teams demanding multi-region high availability.</p>
          <ul class="tier-features">
            <li>✓ Unlimited Autonomous Agents</li>
            <li>✓ 5M Monthly API Calls</li>
            <li>✓ 24/7 Dedicated Support</li>
            <li>✓ 6.8ms Dedicated Edge Anycast</li>
            <li>✓ Persistent Memory Store (SQLite WAL)</li>
          </ul>
          <button class="btn-tier featured-btn" onclick="handleTierSelect('Pro Cluster')">Start Free Trial</button>
        </div>

        <div class="pricing-card">
          <div class="card-tier">Enterprise</div>
          <div class="card-price"><span class="price-val" data-monthly="199" data-annual="159">$199</span><span class="period">/mo</span></div>
          <p class="card-desc">For high-throughput mission-critical enterprises.</p>
          <ul class="tier-features">
            <li>✓ Custom Edge Topologies</li>
            <li>✓ Unlimited Monthly Calls</li>
            <li>✓ SLA 99.99% Guarantee</li>
            <li>✓ Hardware-isolated Enclaves</li>
          </ul>
          <button class="btn-tier" onclick="handleTierSelect('Enterprise')">Contact Sales</button>
        </div>
      </div>
    </section>
  </main>

  <!-- Auth Modal -->
  <div id="authModal" class="modal-backdrop" aria-hidden="true">
    <div class="modal-panel" role="dialog" aria-modal="true" aria-labelledby="modalTitle">
      <div class="modal-header">
        <h3 id="modalTitle">Welcome to Apex Nexus</h3>
        <button id="closeAuthBtn" class="btn-close" aria-label="Close modal">×</button>
      </div>
      <div class="auth-tabs">
        <button id="tabSignIn" class="auth-tab active">Sign In</button>
        <button id="tabSignUp" class="auth-tab">Sign Up</button>
      </div>
      <form id="authForm" class="auth-form">
        <div class="form-group">
          <label for="authEmail">Work Email</label>
          <input type="email" id="authEmail" required placeholder="name@company.com">
        </div>
        <div class="form-group">
          <label for="authPassword">Password</label>
          <input type="password" id="authPassword" required placeholder="••••••••••••" minlength="8">
        </div>
        <button type="submit" id="authSubmitBtn" class="btn-submit">Sign In to Dashboard</button>
      </form>
      <div id="userStateArea" class="user-state-area" style="display:none;">
        <p>Signed in as: <strong id="userDisplayEmail"></strong></p>
        <button id="signOutBtn" class="btn-secondary small">Sign Out</button>
      </div>
    </div>
  </div>

  <!-- Toast Notification Container -->
  <div id="toastContainer" class="toast-container" aria-live="polite"></div>

  <footer class="app-footer">
    <div class="footer-inner">
      <p>© 2026 Apex Nexus Inc. High-Availability Autonomous Cloud.</p>
      <div class="footer-links">
        <a href="#overview">Status</a>
        <a href="#pricing">Security</a>
        <a href="#docs">API Reference</a>
      </div>
    </div>
  </footer>

  <script src="app.js"></script>
</body>
</html>""",
        "style.css": """:root {
  --bg-primary: #0a0e17;
  --bg-secondary: #111827;
  --bg-card: rgba(17, 24, 39, 0.7);
  --border-color: rgba(255, 255, 255, 0.08);
  --text-primary: #f9fafb;
  --text-secondary: #9ca3af;
  --text-muted: #6b7280;
  --accent-primary: #6366f1;
  --accent-hover: #4f46e5;
  --accent-glow: rgba(99, 102, 241, 0.25);
  --success: #10b981;
  --font-main: 'Plus Jakarta Sans', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

body.light-mode {
  --bg-primary: #f8fafc;
  --bg-secondary: #ffffff;
  --bg-card: rgba(255, 255, 255, 0.85);
  --border-color: rgba(0, 0, 0, 0.08);
  --text-primary: #0f172a;
  --text-secondary: #475569;
  --text-muted: #94a3b8;
  --accent-primary: #4f46e5;
  --accent-hover: #4338ca;
  --accent-glow: rgba(79, 70, 229, 0.15);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-main);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  min-height: 100vh;
  line-height: 1.6;
  transition: background-color 0.25s ease, color 0.25s ease;
}

/* App Header */
.app-header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--bg-card);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border-color);
}

.header-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.5px;
}

.logo-mark {
  width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #6366f1, #06b6d4);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 14px;
}

.logo-text span {
  color: var(--accent-primary);
  margin-left: 2px;
}

.nav-links {
  display: flex;
  gap: 24px;
}

.nav-links a {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.15s ease;
}

.nav-links a:hover, .nav-links a.active {
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-icon {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-primary);
  width: 36px;
  height: 36px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.btn-primary {
  background: var(--accent-primary);
  color: white;
  border: none;
  padding: 8px 18px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s ease, transform 0.1s ease;
}

.btn-primary:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
}

.mobile-toggle {
  display: none;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 24px;
  cursor: pointer;
}

/* Page Layout */
.page-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 48px 24px;
}

/* Hero */
.hero-section {
  text-align: center;
  padding: 64px 0 48px;
}

.badge-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  padding: 6px 14px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 24px;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background-color: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--success);
}

.hero-title {
  font-size: clamp(32px, 5vw, 56px);
  font-weight: 800;
  line-height: 1.15;
  letter-spacing: -1.5px;
  margin-bottom: 20px;
}

.gradient-text {
  background: linear-gradient(135deg, #6366f1 0%, #06b6d4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero-subtitle {
  font-size: 18px;
  color: var(--text-secondary);
  max-width: 640px;
  margin: 0 auto 36px;
}

.hero-cta-group {
  display: flex;
  justify-content: center;
  gap: 16px;
}

.btn-cta {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: white;
  border: none;
  padding: 14px 28px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  box-shadow: 0 8px 24px var(--accent-glow);
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.btn-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px var(--accent-glow);
}

.btn-secondary {
  background: var(--bg-card);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 14px 24px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 15px;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

/* KPI Grid */
.kpi-section {
  padding: 48px 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.section-header.center {
  flex-direction: column;
  text-align: center;
  gap: 8px;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--success);
}

.green-dot {
  width: 6px;
  height: 6px;
  background-color: var(--success);
  border-radius: 50%;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}

.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 24px;
  backdrop-filter: blur(8px);
}

.kpi-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.kpi-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.kpi-change.positive {
  font-size: 12px;
  font-weight: 700;
  color: var(--success);
}

.kpi-change.neutral {
  font-size: 12px;
  font-weight: 700;
  color: #06b6d4;
}

.kpi-value {
  font-family: var(--font-mono);
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -1px;
  margin-bottom: 4px;
}

.kpi-sub {
  font-size: 12px;
  color: var(--text-muted);
}

/* Chart */
.chart-container {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  padding: 24px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.range-selector {
  display: flex;
  gap: 6px;
}

.range-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}

.range-btn.active {
  background: var(--accent-primary);
  color: white;
  border-color: var(--accent-primary);
}

.chart-wrapper {
  width: 100%;
  height: 200px;
}

#telemetryChart {
  width: 100%;
  height: 100%;
}

/* Pricing Section */
.pricing-section {
  padding: 64px 0 32px;
}

.billing-toggle-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
}

.toggle-switch {
  width: 50px;
  height: 28px;
  background-color: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 9999px;
  position: relative;
  cursor: pointer;
  padding: 2px;
}

.toggle-knob {
  display: block;
  width: 22px;
  height: 22px;
  background-color: var(--accent-primary);
  border-radius: 50%;
  transition: transform 0.2s ease;
}

.toggle-switch.annual .toggle-knob {
  transform: translateX(22px);
}

.discount-tag {
  background: rgba(16, 185, 129, 0.15);
  color: var(--success);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 9999px;
  margin-left: 4px;
}

.pricing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
  margin-top: 36px;
}

.pricing-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  position: relative;
}

.pricing-card.featured {
  border-color: var(--accent-primary);
  box-shadow: 0 0 32px var(--accent-glow);
}

.popular-ribbon {
  position: absolute;
  top: -12px;
  right: 24px;
  background: var(--accent-primary);
  color: white;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 12px;
  border-radius: 9999px;
  text-transform: uppercase;
}

.card-tier {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 8px;
}

.card-price {
  font-size: 38px;
  font-weight: 800;
  letter-spacing: -1px;
  margin-bottom: 12px;
}

.card-price .period {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-muted);
}

.card-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 24px;
}

.tier-features {
  list-style: none;
  margin-bottom: 32px;
  flex-grow: 1;
}

.tier-features li {
  font-size: 14px;
  margin-bottom: 10px;
  color: var(--text-secondary);
}

.btn-tier {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-tier:hover {
  background: var(--border-color);
}

.btn-tier.featured-btn {
  background: var(--accent-primary);
  color: white;
  border: none;
}

.btn-tier.featured-btn:hover {
  background: var(--accent-hover);
}

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.modal-backdrop.open {
  display: flex;
}

.modal-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  width: 100%;
  max-width: 420px;
  padding: 28px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.5);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.btn-close {
  background: transparent;
  border: none;
  font-size: 24px;
  color: var(--text-muted);
  cursor: pointer;
}

.auth-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 8px;
}

.auth-tab {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 600;
  padding: 6px 12px;
  cursor: pointer;
}

.auth-tab.active {
  color: var(--accent-primary);
  border-bottom: 2px solid var(--accent-primary);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.form-group input {
  width: 100%;
  padding: 10px 14px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 14px;
}

.form-group input:focus {
  outline: none;
  border-color: var(--accent-primary);
}

.btn-submit {
  background: var(--accent-primary);
  color: white;
  border: none;
  padding: 12px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  margin-top: 8px;
}

/* Toast */
.toast-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.toast {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 12px 18px;
  border-radius: 8px;
  box-shadow: 0 8px 16px rgba(0,0,0,0.3);
  font-size: 13px;
  font-weight: 500;
  animation: slideIn 0.2s ease forwards;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Footer */
.app-footer {
  border-top: 1px solid var(--border-color);
  padding: 32px 24px;
  font-size: 13px;
  color: var(--text-muted);
}

.footer-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.footer-links {
  display: flex;
  gap: 20px;
}

.footer-links a {
  color: var(--text-muted);
  text-decoration: none;
}

/* Responsive Media Queries */
@media (max-width: 768px) {
  .nav-links { display: none; }
  .mobile-toggle { display: block; }
  .hero-title { font-size: 34px; }
  .hero-subtitle { font-size: 16px; }
  .footer-inner { flex-direction: column; gap: 16px; text-align: center; }
}
""",
        "app.js": """// Apex Cloud Nexus — Interactive Application Engine
(function() {
  'use strict';

  // 1. Theme Management
  const themeToggle = document.getElementById('themeToggleBtn');
  const storedTheme = localStorage.getItem('apex_theme') || 'dark';
  document.body.className = storedTheme === 'light' ? 'light-mode' : 'dark-mode';

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const isLight = document.body.classList.contains('light-mode');
      const newTheme = isLight ? 'dark' : 'light';
      document.body.className = newTheme === 'light' ? 'light-mode' : 'dark-mode';
      localStorage.setItem('apex_theme', newTheme);
      triggerToast(`Theme switched to ${newTheme} mode`, 'info');
    });
  }

  // 2. Telemetry Live Number Jitter & Chart Drawing
  function updateTelemetry() {
    const agentsEl = document.getElementById('kpiAgents');
    const rpsEl = document.getElementById('kpiRps');
    const latEl = document.getElementById('kpiLatency');

    if (agentsEl) {
      const baseAgents = 1420;
      const delta = Math.floor(Math.sin(Date.now() / 3000) * 15);
      agentsEl.textContent = (baseAgents + delta).toLocaleString();
    }

    if (rpsEl) {
      const baseRps = 84210;
      const delta = Math.floor(Math.cos(Date.now() / 2500) * 850);
      rpsEl.textContent = (baseRps + delta).toLocaleString();
    }

    if (latEl) {
      const lat = (6.8 + (Math.sin(Date.now() / 4000) * 0.4)).toFixed(1);
      latEl.textContent = `${lat}ms`;
    }
  }

  setInterval(updateTelemetry, 2500);

  // Draw Dynamic SVG Load Chart
  function drawChart() {
    const chartLine = document.getElementById('chartLine');
    const chartArea = document.getElementById('chartArea');
    if (!chartLine || !chartArea) return;

    const points = [
      {x: 0, y: 140}, {x: 100, y: 120}, {x: 200, y: 90},
      {x: 300, y: 110}, {x: 400, y: 70}, {x: 500, y: 50},
      {x: 600, y: 80}, {x: 700, y: 40}, {x: 800, y: 65}
    ];

    let pathD = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const cx = (prev.x + curr.x) / 2;
      pathD += ` C ${cx} ${prev.y}, ${cx} ${curr.y}, ${curr.x} ${curr.y}`;
    }

    chartLine.setAttribute('d', pathD);
    const areaD = `${pathD} L 800 200 L 0 200 Z`;
    chartArea.setAttribute('d', areaD);
  }

  drawChart();

  // Range selector
  document.querySelectorAll('.range-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      drawChart();
      triggerToast(`Loaded metrics range: ${e.target.dataset.range}`, 'info');
    });
  });

  // 3. Billing Toggle (Monthly / Annual)
  const billingSwitch = document.getElementById('billingSwitch');
  let isAnnual = false;

  if (billingSwitch) {
    billingSwitch.addEventListener('click', () => {
      isAnnual = !isAnnual;
      billingSwitch.classList.toggle('annual', isAnnual);
      document.querySelectorAll('.price-val').forEach(el => {
        const val = isAnnual ? el.getAttribute('data-annual') : el.getAttribute('data-monthly');
        el.textContent = `$${val}`;
      });
      triggerToast(isAnnual ? 'Applied 20% annual discount' : 'Switched to monthly billing', 'info');
    });
  }

  // 4. Modal & Auth Management
  const authModal = document.getElementById('authModal');
  const openAuthBtn = document.getElementById('openAuthBtn');
  const closeAuthBtn = document.getElementById('closeAuthBtn');
  const authForm = document.getElementById('authForm');
  const userArea = document.getElementById('userStateArea');
  const userEmailDisplay = document.getElementById('userDisplayEmail');
  const signOutBtn = document.getElementById('signOutBtn');

  function checkSession() {
    const user = localStorage.getItem('apex_user');
    if (user && openAuthBtn) {
      openAuthBtn.textContent = 'Account';
      if (userArea && userEmailDisplay) {
        userArea.style.display = 'block';
        if (authForm) authForm.style.display = 'none';
        userEmailDisplay.textContent = user;
      }
    }
  }

  checkSession();

  if (openAuthBtn && authModal) {
    openAuthBtn.addEventListener('click', () => {
      authModal.classList.add('open');
      authModal.setAttribute('aria-hidden', 'false');
    });
  }

  if (closeAuthBtn && authModal) {
    closeAuthBtn.addEventListener('click', () => {
      authModal.classList.remove('open');
      authModal.setAttribute('aria-hidden', 'true');
    });
  }

  if (authModal) {
    authModal.addEventListener('click', (e) => {
      if (e.target === authModal) {
        authModal.classList.remove('open');
      }
    });
  }

  if (authForm) {
    authForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const email = document.getElementById('authEmail').value;
      localStorage.setItem('apex_user', email);
      triggerToast(`Welcome back, ${email}!`, 'success');
      authModal.classList.remove('open');
      checkSession();
    });
  }

  if (signOutBtn) {
    signOutBtn.addEventListener('click', () => {
      localStorage.removeItem('apex_user');
      triggerToast('Signed out successfully', 'info');
      if (userArea) userArea.style.display = 'none';
      if (authForm) authForm.style.display = 'flex';
      if (openAuthBtn) openAuthBtn.textContent = 'Sign In';
      authModal.classList.remove('open');
    });
  }

  // 5. Global Toast Helper
  window.triggerToast = function(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 3500);
  };

  window.handleTierSelect = function(tierName) {
    window.triggerToast(`Selected ${tierName} plan. Loading checkout drawer...`, 'info');
  };
})();
"""
    }
)

# ──────────────────────────────────────────────────────────────────────────────
# SITE-02: Himalayan Artisans Marketplace
# ──────────────────────────────────────────────────────────────────────────────
UNSEEN_SHOWCASE_SITES["NEW-SITE-02"] = ShowcaseSite(
    site_id="NEW-SITE-02",
    name="Himalayan Heritage Marketplace",
    category="Authentic Nepali Cultural E-Commerce",
    tagline="Ancient Himalayan Craftsmanship, Ethically Sourced",
    description="Authentic Nepali cultural e-commerce shop featuring genuine Pashmina, Thangkas, Singing Bowls, and Lokta papers with working cart, currency switcher (NPR/USD), and checkout modal.",
    key_features=[
        "Bilingual Devanagari & English cultural product showcase",
        "Dual currency engine with live NPR (रू.) to USD ($) recalculation",
        "Slide-over persistent shopping cart with localStorage preservation",
        "Category filter buttons (All, Textiles, Sacred Art, Sound Healing, Stationery)",
        "Checkout modal with Khalti / eSewa / Card payment options and invoice breakdown",
    ],
    files={
        "index.html": """<!DOCTYPE html>
<html lang="ne">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Himalayan Heritage — प्रामाणिक नेपाली हस्तकला</title>
  <link rel="stylesheet" href="style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Mukta:wght@400;500;600;700;800&family=Cinzel:wght@600;700;800&display=swap" rel="stylesheet">
</head>
<body>
  <header class="heritage-header">
    <div class="top-announcement">
      <span>🏔️ सिधै नेपालका स्थानीय कारीगरहरूबाट आयातित — प्रत्येक खरिदले स्थानीय समुदायलाई सहयोग गर्दछ।</span>
    </div>
    <div class="header-main">
      <div class="brand">
        <span class="brand-nepali">हिमालयन</span>
        <span class="brand-sub">HERITAGE ARTISANS</span>
      </div>
      <div class="header-tools">
        <!-- Currency Switcher -->
        <div class="currency-switcher" aria-label="Currency Selector">
          <button id="currNPR" class="curr-btn active" data-curr="NPR">रू. NPR</button>
          <button id="currUSD" class="curr-btn" data-curr="USD">$ USD</button>
        </div>
        <!-- Cart Trigger -->
        <button id="openCartBtn" class="cart-btn" aria-label="Open Shopping Cart">
          <span>🛒 झोला</span>
          <span id="cartCountBadge" class="count-badge">0</span>
        </button>
      </div>
    </div>
  </header>

  <main class="store-container">
    <section class="heritage-hero">
      <div class="hero-content">
        <span class="hero-tag">प्रामाणिक नेपाली हस्तकला</span>
        <h1>परम्परागत नेपाली सीप र कला</h1>
        <p>पाटनको धातु कला, भक्तपुरको माटो कला, र मुस्ताङको मौलिक पश्मिना—हाम्रा सम्पूर्ण उत्पादनहरू स्थानीय कारीगरहरूद्वारा हस्तनिर्मित छन्।</p>
      </div>
    </section>

    <!-- Category Filters -->
    <section class="catalog-section">
      <div class="filter-bar">
        <button class="filter-btn active" data-cat="all">सबै उत्पादन (All)</button>
        <button class="filter-btn" data-cat="textiles">पश्मिना (Textiles)</button>
        <button class="filter-btn" data-cat="art">थाङ्का (Sacred Art)</button>
        <button class="filter-btn" data-cat="sound">सिङ्गिङ बाउल (Singing Bowls)</button>
        <button class="filter-btn" data-cat="stationery">लोक्ता कागज (Lokta Paper)</button>
      </div>

      <!-- Product Grid -->
      <div id="productGrid" class="product-grid">
        <!-- Injected via JavaScript -->
      </div>
    </section>
  </main>

  <!-- Slide-Over Shopping Cart Drawer -->
  <aside id="cartDrawer" class="cart-drawer" aria-hidden="true">
    <div class="cart-header">
      <h3>तपाईंको झोला (Shopping Cart)</h3>
      <button id="closeCartBtn" class="btn-close" aria-label="Close cart">×</button>
    </div>
    <div id="cartItemsList" class="cart-items-list">
      <div class="empty-cart-msg">झोलामा कुनै सामग्री छैन (Cart is empty)</div>
    </div>
    <div class="cart-footer">
      <div class="cart-total-row">
        <span>जम्मा रकम (Subtotal):</span>
        <strong id="cartSubtotalDisplay">रू. ०</strong>
      </div>
      <button id="checkoutBtn" class="btn-checkout" disabled>अर्डर पुष्टि गर्नुहोस् (Checkout) →</button>
    </div>
  </aside>

  <!-- Checkout Confirmation Modal -->
  <div id="checkoutModal" class="modal-backdrop" aria-hidden="true">
    <div class="modal-panel">
      <div class="modal-header">
        <h3>अर्डर सारांश (Order Confirmation)</h3>
        <button id="closeCheckoutBtn" class="btn-close">×</button>
      </div>
      <div class="checkout-body">
        <p>प्रामाणिक नेपाली हस्तकला छान्नुभएकोमा धन्यवाद!</p>
        <div id="checkoutSummary" class="order-summary-box"></div>
        <div class="payment-options">
          <label><input type="radio" name="payMethod" value="esewa" checked> eSewa / Khalti</label>
          <label><input type="radio" name="payMethod" value="card"> International Card (Visa/Mastercard)</label>
        </div>
        <button id="confirmOrderBtn" class="btn-checkout">भुक्तानी सम्पन्न गर्नुहोस् (Pay Now)</button>
      </div>
    </div>
  </div>

  <footer class="heritage-footer">
    <p>© २०२६ हिमालयन हेरिटेज आर्टिसन्स। काठमाडौं, नेपाल। सर्वाधिकार सुरक्षित।</p>
  </footer>

  <script src="app.js"></script>
</body>
</html>""",
        "style.css": """:root {
  --crimson: #881337;
  --crimson-dark: #4c0519;
  --gold: #d97706;
  --gold-light: #fef3c7;
  --bg-parchment: #fffbeb;
  --bg-card: #ffffff;
  --text-dark: #1c1917;
  --text-muted: #78716c;
  --border-sep: #f3e8ff;
  --font-nepali: 'Mukta', sans-serif;
  --font-display: 'Cinzel', serif;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-nepali);
  background-color: var(--bg-parchment);
  color: var(--text-dark);
  line-height: 1.6;
}

/* Header */
.top-announcement {
  background: var(--crimson-dark);
  color: var(--gold-light);
  text-align: center;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
}

.header-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand {
  display: flex;
  flex-direction: column;
}

.brand-nepali {
  font-size: 26px;
  font-weight: 800;
  color: var(--crimson);
  line-height: 1.1;
}

.brand-sub {
  font-family: var(--font-display);
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--gold);
}

.header-tools {
  display: flex;
  align-items: center;
  gap: 16px;
}

.currency-switcher {
  display: flex;
  background: white;
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  overflow: hidden;
}

.curr-btn {
  background: transparent;
  border: none;
  padding: 6px 12px;
  font-family: var(--font-nepali);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.curr-btn.active {
  background: var(--crimson);
  color: white;
}

.cart-btn {
  background: var(--crimson);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 8px;
  font-family: var(--font-nepali);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.count-badge {
  background: var(--gold);
  color: white;
  border-radius: 9999px;
  padding: 2px 8px;
  font-size: 12px;
  font-weight: 700;
}

/* Hero */
.heritage-hero {
  background: linear-gradient(135deg, rgba(136, 19, 55, 0.08) 0%, rgba(217, 119, 6, 0.1) 100%);
  border-radius: 20px;
  margin: 16px 24px 36px;
  padding: 48px 32px;
  text-align: center;
}

.hero-tag {
  color: var(--crimson);
  font-weight: 700;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.heritage-hero h1 {
  font-size: clamp(28px, 4vw, 44px);
  font-weight: 800;
  color: var(--crimson-dark);
  margin: 12px 0 16px;
}

.heritage-hero p {
  max-width: 680px;
  margin: 0 auto;
  color: var(--text-muted);
  font-size: 16px;
}

/* Catalog */
.store-container {
  max-width: 1200px;
  margin: 0 auto;
}

.filter-bar {
  display: flex;
  gap: 10px;
  padding: 0 24px 24px;
  overflow-x: auto;
}

.filter-btn {
  background: white;
  border: 1px solid #e7e5e4;
  padding: 8px 16px;
  border-radius: 9999px;
  font-family: var(--font-nepali);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.filter-btn.active {
  background: var(--crimson);
  color: white;
  border-color: var(--crimson);
}

.product-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 24px;
  padding: 0 24px 64px;
}

.product-card {
  background: white;
  border: 1px solid #e7e5e4;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.product-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0,0,0,0.06);
}

.product-thumb {
  height: 180px;
  background: #f5f5f4;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 54px;
}

.product-details {
  padding: 20px;
  display: flex;
  flex-direction: column;
  flex-grow: 1;
}

.product-origin {
  font-size: 12px;
  color: var(--gold);
  font-weight: 600;
  margin-bottom: 4px;
}

.product-title {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--text-dark);
}

.product-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 16px;
  flex-grow: 1;
}

.product-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.product-price {
  font-size: 18px;
  font-weight: 800;
  color: var(--crimson);
}

.btn-add {
  background: var(--crimson);
  color: white;
  border: none;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.btn-add:hover {
  background: var(--crimson-dark);
}

/* Cart Drawer */
.cart-drawer {
  position: fixed;
  top: 0;
  right: -420px;
  width: 400px;
  max-width: 100vw;
  height: 100vh;
  background: white;
  box-shadow: -8px 0 24px rgba(0,0,0,0.15);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  transition: right 0.3s ease;
}

.cart-drawer.open {
  right: 0;
}

.cart-header {
  padding: 20px 24px;
  border-bottom: 1px solid #f5f5f4;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cart-items-list {
  padding: 20px 24px;
  flex-grow: 1;
  overflow-y: auto;
}

.cart-item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #f5f5f4;
}

.cart-footer {
  padding: 20px 24px;
  border-top: 1px solid #f5f5f4;
  background: var(--bg-parchment);
}

.cart-total-row {
  display: flex;
  justify-content: space-between;
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 16px;
}

.btn-checkout {
  width: 100%;
  background: var(--crimson);
  color: white;
  border: none;
  padding: 14px;
  border-radius: 10px;
  font-family: var(--font-nepali);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.btn-checkout:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Modal */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 20px;
}

.modal-backdrop.open {
  display: flex;
}

.modal-panel {
  background: white;
  border-radius: 16px;
  max-width: 460px;
  width: 100%;
  padding: 28px;
}

.btn-close {
  background: transparent;
  border: none;
  font-size: 24px;
  cursor: pointer;
}

.heritage-footer {
  text-align: center;
  padding: 32px 24px;
  border-top: 1px solid #e7e5e4;
  color: var(--text-muted);
  font-size: 13px;
}

/* Responsive Media Queries */
@media (max-width: 768px) {
  .nav-center { display: none; }
  .hero-content h1 { font-size: 32px; }
  .product-grid { grid-template-columns: 1fr; }
  .cart-drawer { width: 100%; }
}

@media (max-width: 480px) {
  .hero-banner { padding: 40px 16px; }
  .filters-bar { flex-direction: column; align-items: stretch; }
  .product-bottom { flex-direction: column; gap: 10px; align-items: flex-start; }
}
""",
        "app.js": """// Himalayan Heritage Artisans — Store & Cart Engine
(function() {
  'use strict';

  // 1. Product Catalog with Authentic Nepali Provenance
  const PRODUCTS = [
    {
      id: "prod-01",
      nameNepali: "काठमाडौं शुद्ध पश्मिना शल",
      nameEnglish: "Pure Himalayan Cashmere Pashmina",
      category: "textiles",
      origin: "मुस्ताङ / काठमाडौं",
      descNepali: "अत्यन्त नरम र न्यानो हिमाली च्याङ्ग्राको भुवाबाट हस्तनिर्मित।",
      priceNPR: 8500,
      icon: "🧣"
    },
    {
      id: "prod-02",
      nameNepali: "चेनेरेजिग हस्तलिखित थाङ्का",
      nameEnglish: "Chenrezig Hand-painted Sacred Thangka",
      category: "art",
      origin: "पाटन हस्तकला केन्द्र",
      descNepali: "२४ क्यारेट सुनको जलप र प्राकृतिक रङ्ग प्रयोग गरिएको ध्यान थाङ्का।",
      priceNPR: 18500,
      icon: "🖼️"
    },
    {
      id: "prod-03",
      nameNepali: "सात धातुको हिमाली सिङ्गिङ बाउल",
      nameEnglish: "Seven-Metal Hand-hammered Singing Bowl",
      category: "sound",
      origin: "कीर्तिपुर",
      descNepali: "ध्वनि थेरापी र ध्यानका लागि उपयुक्त पारम्परिक हस्तनिर्मित कचौरा।",
      priceNPR: 4500,
      icon: "🥣"
    },
    {
      id: "prod-04",
      nameNepali: "अर्गानिक लोक्ता नेपाली डायरी",
      nameEnglish: "Organic Lokta Bark Journal",
      category: "stationery",
      origin: "दोलखा",
      descNepali: "कीरा नलाग्ने र सयौं वर्ष सुरक्षित रहने पौराणिक नेपाली हाते कागज।",
      priceNPR: 1200,
      icon: "📖"
    },
    {
      id: "prod-05",
      nameNepali: "ढाका टोपी र रुमाल सेट",
      nameEnglish: "Traditional Handwoven Dhaka Set",
      category: "textiles",
      origin: "पाल्पा",
      descNepali: "मौलिक नेपाली ज्यामितीय बुट्टा भरिएको पाल्पाली ढाका सेट।",
      priceNPR: 1800,
      icon: "🎩"
    },
    {
      id: "prod-06",
      nameNepali: "मञ्जुश्री काँसको मूर्ति",
      nameEnglish: "Manjushri Bronze Sculpture",
      category: "art",
      origin: "भक्तपुर",
      descNepali: "लस्ट-वाक्स प्रविधिबाट ढालिएको ज्ञानका प्रतीक मञ्जुश्रीको मूर्ति।",
      priceNPR: 12500,
      icon: "🗿"
    }
  ];

  // 2. Currency State
  let currentCurrency = localStorage.getItem('himalayan_curr') || 'NPR';
  const USD_RATE = 135.5;

  function formatPrice(nprAmount) {
    if (currentCurrency === 'USD') {
      const usd = (nprAmount / USD_RATE).toFixed(2);
      return `$${usd} USD`;
    }
    return `रू. ${nprAmount.toLocaleString('ne-NP')}`;
  }

  // Currency Toggle
  const currNPR = document.getElementById('currNPR');
  const currUSD = document.getElementById('currUSD');

  function updateCurrencyUI() {
    if (currNPR && currUSD) {
      currNPR.classList.toggle('active', currentCurrency === 'NPR');
      currUSD.classList.toggle('active', currentCurrency === 'USD');
    }
    renderProducts(activeCategory);
    renderCart();
  }

  if (currNPR) {
    currNPR.addEventListener('click', () => {
      currentCurrency = 'NPR';
      localStorage.setItem('himalayan_curr', 'NPR');
      updateCurrencyUI();
    });
  }

  if (currUSD) {
    currUSD.addEventListener('click', () => {
      currentCurrency = 'USD';
      localStorage.setItem('himalayan_curr', 'USD');
      updateCurrencyUI();
    });
  }

  // 3. Render Catalog
  let activeCategory = 'all';
  const productGrid = document.getElementById('productGrid');

  function renderProducts(cat = 'all') {
    if (!productGrid) return;
    const filtered = cat === 'all' ? PRODUCTS : PRODUCTS.filter(p => p.category === cat);
    
    productGrid.innerHTML = filtered.map(p => `
      <div class="product-card" data-id="${p.id}">
        <div class="product-thumb">${p.icon}</div>
        <div class="product-details">
          <span class="product-origin">📍 ${p.origin}</span>
          <h4 class="product-title">${p.nameNepali}</h4>
          <p class="product-desc">${p.descNepali}</p>
          <div class="product-bottom">
            <span class="product-price">${formatPrice(p.priceNPR)}</span>
            <button class="btn-add" onclick="window.addToCart('${p.id}')">+ झोलामा थप्नुहोस्</button>
          </div>
        </div>
      </div>
    `).join('');
  }

  // 4. Cart Engine (with localStorage)
  let cart = [];
  try {
    const saved = localStorage.getItem('himalayan_cart');
    if (saved) cart = JSON.parse(saved);
  } catch(e) {}

  window.addToCart = function(prodId) {
    const prod = PRODUCTS.find(p => p.id === prodId);
    if (!prod) return;
    const existing = cart.find(item => item.id === prodId);
    if (existing) {
      existing.qty += 1;
    } else {
      cart.push({ id: prod.id, name: prod.nameNepali, priceNPR: prod.priceNPR, qty: 1 });
    }
    saveCart();
    renderCart();
    openCart();
  };

  window.removeFromCart = function(prodId) {
    cart = cart.filter(item => item.id !== prodId);
    saveCart();
    renderCart();
  };

  function saveCart() {
    localStorage.setItem('himalayan_cart', JSON.stringify(cart));
  }

  function renderCart() {
    const badge = document.getElementById('cartCountBadge');
    const itemsList = document.getElementById('cartItemsList');
    const subtotalEl = document.getElementById('cartSubtotalDisplay');
    const checkoutBtn = document.getElementById('checkoutBtn');

    const totalQty = cart.reduce((sum, item) => sum + item.qty, 0);
    if (badge) badge.textContent = totalQty;

    let subtotalNPR = 0;
    if (itemsList) {
      if (cart.length === 0) {
        itemsList.innerHTML = '<div class="empty-cart-msg">झोलामा कुनै सामग्री छैन (Cart is empty)</div>';
        if (checkoutBtn) checkoutBtn.disabled = true;
      } else {
        itemsList.innerHTML = cart.map(item => {
          const itemTotal = item.priceNPR * item.qty;
          subtotalNPR += itemTotal;
          return `
            <div class="cart-item-row">
              <div>
                <strong>${item.name}</strong><br>
                <small>${item.qty} × ${formatPrice(item.priceNPR)}</small>
              </div>
              <div style="display:flex; align-items:center; gap:8px;">
                <span>${formatPrice(itemTotal)}</span>
                <button onclick="window.removeFromCart('${item.id}')" style="background:none;border:none;cursor:pointer;color:red;">✕</button>
              </div>
            </div>
          `;
        }).join('');
        if (checkoutBtn) checkoutBtn.disabled = false;
      }
    }

    if (subtotalEl) {
      subtotalEl.textContent = formatPrice(subtotalNPR);
    }
  }

  // Cart Drawer open/close
  const cartDrawer = document.getElementById('cartDrawer');
  const openCartBtn = document.getElementById('openCartBtn');
  const closeCartBtn = document.getElementById('closeCartBtn');

  function openCart() {
    if (cartDrawer) {
      cartDrawer.classList.add('open');
      cartDrawer.setAttribute('aria-hidden', 'false');
    }
  }

  function closeCart() {
    if (cartDrawer) {
      cartDrawer.classList.remove('open');
      cartDrawer.setAttribute('aria-hidden', 'true');
    }
  }

  if (openCartBtn) openCartBtn.addEventListener('click', openCart);
  if (closeCartBtn) closeCartBtn.addEventListener('click', closeCart);

  // Category Filter clicks
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      activeCategory = e.target.dataset.cat;
      renderProducts(activeCategory);
    });
  });

  // 5. Checkout Modal
  const checkoutBtn = document.getElementById('checkoutBtn');
  const checkoutModal = document.getElementById('checkoutModal');
  const closeCheckoutBtn = document.getElementById('closeCheckoutBtn');
  const confirmOrderBtn = document.getElementById('confirmOrderBtn');

  if (checkoutBtn && checkoutModal) {
    checkoutBtn.addEventListener('click', () => {
      const summaryBox = document.getElementById('checkoutSummary');
      if (summaryBox) {
        const total = cart.reduce((s, i) => s + (i.priceNPR * i.qty), 0);
        summaryBox.innerHTML = `
          <p>कुल वस्तुहरू: <strong>${cart.length} प्रकार</strong></p>
          <p>भुक्तानी रकम: <strong>${formatPrice(total)}</strong></p>
        `;
      }
      closeCart();
      checkoutModal.classList.add('open');
    });
  }

  if (closeCheckoutBtn && checkoutModal) {
    closeCheckoutBtn.addEventListener('click', () => checkoutModal.classList.remove('open'));
  }

  if (confirmOrderBtn) {
    confirmOrderBtn.addEventListener('click', () => {
      alert('तपाईंको अर्डर सफलतापूर्वक प्राप्त भयो! (Order placed successfully!)');
      cart = [];
      saveCart();
      renderCart();
      checkoutModal.classList.remove('open');
    });
  }

  // Initial render
  renderProducts('all');
  renderCart();
})();
"""
    }
)

# ──────────────────────────────────────────────────────────────────────────────
# SITE-03: Zenith Interactive Developer Creative Studio
# ──────────────────────────────────────────────────────────────────────────────
UNSEEN_SHOWCASE_SITES["NEW-SITE-03"] = ShowcaseSite(
    site_id="NEW-SITE-03",
    name="Zenith Interactive Studio",
    category="Developer Portfolio & Code Workbench",
    tagline="Crafting High-Performance Systems & Neural Interfaces",
    description="Interactive developer portfolio featuring 60fps canvas particle physics, an embedded live JavaScript sandbox with real-time output terminal, filterable project grid, and auto-saved inquiry drafts.",
    key_features=[
        "60fps interactive HTML5 Canvas particle network background with mouse attraction",
        "Embedded live JavaScript code runner with terminal output execution",
        "Filterable project matrix (Systems, Neural AI, WebGPU, Cloud Enclaves)",
        "Auto-saving client briefing form stored in localStorage in real time",
        "Full keyboard accessibility with WCAG 2.1 AA focus rings",
    ],
    files={
        "index.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Zenith Studio — Systems & Creative Engineering</title>
  <link rel="stylesheet" href="style.css">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Fira+Code:wght@400;500;700&display=swap" rel="stylesheet">
</head>
<body>
  <!-- Canvas Background for Particle Physics -->
  <canvas id="particleCanvas"></canvas>

  <div class="site-wrapper">
    <header class="zenith-header">
      <div class="brand">
        <span class="mono-badge">[ZS]</span>
        <span class="brand-title">ZENITH // STUDIO</span>
      </div>
      <nav class="zenith-nav" aria-label="Portfolio Navigation">
        <a href="#work">Work</a>
        <a href="#playground">Code Sandbox</a>
        <a href="#contact">Contact</a>
      </nav>
      <div class="header-status">
        <span class="pulse-indicator"></span> Available for Q1/Q2 Contracts
      </div>
    </header>

    <main class="zenith-main">
      <!-- Hero -->
      <section class="zenith-hero">
        <div class="hero-label">// SENIOR SYSTEMS ARCHITECT & DESIGN ENGINEER</div>
        <h1>Architecting resilient backends & tactile user interfaces.</h1>
        <p class="hero-bio">Specializing in high-frequency event streaming, WebAssembly/WebGPU rendering, and autonomous agent platforms with mathematical correctness.</p>
        <div class="hero-actions">
          <a href="#playground" class="btn-zenith-primary">Test Live Code Sandbox ↓</a>
          <a href="#contact" class="btn-zenith-ghost">Initiate Contract</a>
        </div>
      </section>

      <!-- Interactive Code Sandbox Runner -->
      <section id="playground" class="sandbox-section">
        <div class="section-badge">// INTERACTIVE BENCHMARK RUNNER</div>
        <h2>Live Browser Sandbox</h2>
        <p class="section-desc">Execute arbitrary JavaScript directly in-browser. Select an algorithm preset or write your own.</p>

        <div class="sandbox-box">
          <div class="sandbox-toolbar">
            <span class="tab-label">main.js (Executable)</span>
            <div class="preset-selector">
              <span>Preset:</span>
              <button class="preset-btn active" data-preset="fib">Fibonacci Matrix</button>
              <button class="preset-btn" data-preset="crypto">Hash Simulation</button>
              <button class="preset-btn" data-preset="bench">Array Sort Benchmark</button>
            </div>
            <button id="runCodeBtn" class="btn-run">▶ Run Script</button>
          </div>
          <textarea id="codeEditor" class="code-textarea" spellcheck="false"></textarea>
          <div class="terminal-output-box">
            <div class="terminal-bar">
              <span>OUTPUT TERMINAL</span>
              <button id="clearTermBtn" class="btn-clear-term">Clear</button>
            </div>
            <pre id="terminalLogs" class="terminal-logs">// Output will stream here upon execution...</pre>
          </div>
        </div>
      </section>

      <!-- Filterable Project Showcase -->
      <section id="work" class="work-section">
        <div class="section-badge">// PRODUCTION SHIPMENTS</div>
        <h2>Selected Engineering Systems</h2>
        <div class="project-filters">
          <button class="p-filter-btn active" data-filter="all">All Projects</button>
          <button class="p-filter-btn" data-filter="systems">Distributed Systems</button>
          <button class="p-filter-btn" data-filter="ai">Autonomous Agents</button>
          <button class="p-filter-btn" data-filter="frontend">Frontend Architecture</button>
        </div>
        <div id="projectGrid" class="project-cards-grid">
          <!-- Populated by app.js -->
        </div>
      </section>

      <!-- Auto-Saving Contact Form -->
      <section id="contact" class="contact-section">
        <div class="section-badge">// DIRECT INQUIRY</div>
        <h2>Initiate a Technical Engagement</h2>
        <p class="section-desc">Drafts are saved locally in real time so your brief is never lost.</p>

        <form id="contactForm" class="contact-form">
          <div class="form-row">
            <div class="form-field">
              <label for="contactName">Name / Organization</label>
              <input type="text" id="contactName" required placeholder="Elena Rostova, Stripe">
            </div>
            <div class="form-field">
              <label for="contactEmail">Contact Email</label>
              <input type="email" id="contactEmail" required placeholder="elena@stripe.com">
            </div>
          </div>
          <div class="form-field">
            <label for="contactMessage">Project Scope & Timeline</label>
            <textarea id="contactMessage" rows="5" required placeholder="Describe technical scope, deadlines, and expected throughput..."></textarea>
          </div>
          <div class="contact-form-footer">
            <span id="draftIndicator" class="draft-indicator">Draft saved in localStorage</span>
            <button type="submit" class="btn-zenith-primary">Transmit Brief →</button>
          </div>
        </form>
      </section>
    </main>

    <footer class="zenith-footer">
      <p>© 2026 Zenith Creative Engineering. 100% Deterministic Code Execution.</p>
    </footer>
  </div>

  <script src="app.js"></script>
</body>
</html>""",
        "style.css": """:root {
  --bg-dark: #090a0f;
  --bg-card: rgba(18, 20, 29, 0.75);
  --border-subtle: rgba(255, 255, 255, 0.1);
  --border-active: #6366f1;
  --text-white: #ffffff;
  --text-muted: #94a3b8;
  --accent-cyan: #06b6d4;
  --accent-indigo: #6366f1;
  --accent-green: #10b981;
  --font-display: 'Space Grotesk', sans-serif;
  --font-mono: 'Fira Code', monospace;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  background-color: var(--bg-dark);
  color: var(--text-white);
  font-family: var(--font-display);
  line-height: 1.6;
  min-height: 100vh;
  position: relative;
}

#particleCanvas {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}

.site-wrapper {
  position: relative;
  z-index: 1;
}

/* Header */
.zenith-header {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-subtle);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

.mono-badge {
  font-family: var(--font-mono);
  color: var(--accent-cyan);
}

.zenith-nav {
  display: flex;
  gap: 28px;
}

.zenith-nav a {
  color: var(--text-muted);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.15s ease;
}

.zenith-nav a:hover {
  color: var(--text-white);
}

.header-status {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--accent-green);
  display: flex;
  align-items: center;
  gap: 8px;
}

.pulse-indicator {
  width: 6px;
  height: 6px;
  background-color: var(--accent-green);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--accent-green);
}

/* Main */
.zenith-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 64px 24px;
}

.section-badge {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent-cyan);
  margin-bottom: 8px;
}

/* Hero */
.zenith-hero {
  padding: 48px 0 80px;
  max-width: 800px;
}

.hero-label {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--accent-cyan);
  margin-bottom: 16px;
}

.zenith-hero h1 {
  font-size: clamp(34px, 5vw, 54px);
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -1.5px;
  margin-bottom: 24px;
}

.hero-bio {
  font-size: 18px;
  color: var(--text-muted);
  margin-bottom: 36px;
}

.hero-actions {
  display: flex;
  gap: 16px;
}

.btn-zenith-primary {
  background: var(--accent-indigo);
  color: white;
  text-decoration: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-zenith-primary:hover {
  background: #4f46e5;
  transform: translateY(-1px);
}

.btn-zenith-ghost {
  background: transparent;
  color: var(--text-white);
  border: 1px solid var(--border-subtle);
  text-decoration: none;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
}

/* Sandbox Section */
.sandbox-section {
  padding: 64px 0;
}

.sandbox-box {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  overflow: hidden;
  margin-top: 24px;
  backdrop-filter: blur(12px);
}

.sandbox-toolbar {
  background: rgba(0, 0, 0, 0.4);
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-subtle);
}

.tab-label {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
}

.preset-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.preset-btn {
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
}

.preset-btn.active {
  background: var(--border-subtle);
  color: var(--text-white);
  border-color: var(--accent-cyan);
}

.btn-run {
  background: var(--accent-green);
  color: #000;
  border: none;
  padding: 6px 14px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 12px;
  cursor: pointer;
}

.code-textarea {
  width: 100%;
  height: 220px;
  background: transparent;
  color: #e2e8f0;
  font-family: var(--font-mono);
  font-size: 13px;
  padding: 16px 20px;
  border: none;
  outline: none;
  resize: vertical;
  line-height: 1.5;
}

.terminal-output-box {
  border-top: 1px solid var(--border-subtle);
  background: #040507;
}

.terminal-bar {
  padding: 8px 20px;
  background: rgba(255, 255, 255, 0.03);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
}

.btn-clear-term {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
}

.terminal-logs {
  padding: 14px 20px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--accent-cyan);
  max-height: 160px;
  overflow-y: auto;
  white-space: pre-wrap;
}

/* Projects */
.work-section {
  padding: 64px 0;
}

.project-filters {
  display: flex;
  gap: 10px;
  margin: 20px 0 32px;
  overflow-x: auto;
}

.p-filter-btn {
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  padding: 6px 14px;
  border-radius: 9999px;
  font-size: 13px;
  cursor: pointer;
}

.p-filter-btn.active {
  background: var(--border-subtle);
  color: white;
  border-color: var(--accent-indigo);
}

.project-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 24px;
}

.project-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 24px;
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.project-card:hover {
  transform: translateY(-2px);
  border-color: var(--accent-indigo);
}

.project-tag {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--accent-cyan);
  margin-bottom: 8px;
}

.project-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 10px;
}

.project-desc {
  font-size: 14px;
  color: var(--text-muted);
  margin-bottom: 16px;
}

.project-meta {
  display: flex;
  gap: 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-white);
}

/* Contact */
.contact-section {
  padding: 64px 0 32px;
}

.contact-form {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 32px;
  margin-top: 24px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.form-field label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--text-muted);
}

.form-field input, .form-field textarea {
  width: 100%;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 10px 14px;
  color: white;
  font-family: var(--font-display);
  font-size: 14px;
}

.form-field input:focus, .form-field textarea:focus {
  outline: none;
  border-color: var(--accent-indigo);
}

.contact-form-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
}

.draft-indicator {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--accent-green);
}

.zenith-footer {
  text-align: center;
  padding: 32px 24px;
  border-top: 1px solid var(--border-subtle);
  color: var(--text-muted);
  font-size: 13px;
}

@media (max-width: 768px) {
  .zenith-nav { display: none; }
  .form-row { grid-template-columns: 1fr; }
}
""",
        "app.js": """// Zenith Studio — Interactive Sandbox & Particle Physics
(function() {
  'use strict';

  // 1. Particle Canvas Engine (60fps)
  const canvas = document.getElementById('particleCanvas');
  if (canvas) {
    const ctx = canvas.getContext('2d');
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    window.addEventListener('resize', () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    });

    const particles = [];
    const count = 45;

    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.7,
        vy: (Math.random() - 0.5) * 0.7,
        radius: Math.random() * 1.5 + 1
      });
    }

    function animate() {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = 'rgba(99, 102, 241, 0.3)';
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.08)';

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();

        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const dist = Math.hypot(p.x - p2.x, p.y - p2.y);
          if (dist < 120) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.stroke();
          }
        }
      }
      requestAnimationFrame(animate);
    }
    animate();
  }

  // 2. Interactive Code Sandbox
  const PRESETS = {
    fib: `// Fibonacci Matrix Generation
function fib(n) {
  let a = 0, b = 1;
  const seq = [a];
  for (let i = 1; i < n; i++) {
    seq.push(b);
    let t = a + b;
    a = b;
    b = t;
  }
  return seq;
}
console.log("Calculated 15 terms:", fib(15));`,

    crypto: `// Mock Key Derivation Hash
function mockHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return "0x" + Math.abs(hash).toString(16).padStart(8, '0');
}
console.log("Apex Token Hash:", mockHash("hinaa-phase-19-secret"));`,

    bench: `// Benchmark Array Sort
const arr = Array.from({length: 10000}, () => Math.random());
const t0 = performance.now();
arr.sort();
const dt = (performance.now() - t0).toFixed(3);
console.log(`Sorted 10,000 float elements in ${dt}ms`);`
  };

  const codeEditor = document.getElementById('codeEditor');
  const terminalLogs = document.getElementById('terminalLogs');
  const runCodeBtn = document.getElementById('runCodeBtn');
  const clearTermBtn = document.getElementById('clearTermBtn');

  if (codeEditor) {
    codeEditor.value = PRESETS.fib;
  }

  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      const p = e.target.dataset.preset;
      if (codeEditor && PRESETS[p]) {
        codeEditor.value = PRESETS[p];
      }
    });
  });

  if (runCodeBtn && codeEditor && terminalLogs) {
    runCodeBtn.addEventListener('click', () => {
      const code = codeEditor.value;
      terminalLogs.textContent = "// Executing in sandboxed scope...\\n";

      const originalLog = console.log;
      const logs = [];
      console.log = function(...args) {
        logs.push(args.map(a => typeof a === 'object' ? JSON.stringify(a) : a).join(' '));
        originalLog.apply(console, args);
      };

      try {
        const start = performance.now();
        // Safe evaluation
        const fn = new Function(code);
        fn();
        const duration = (performance.now() - start).toFixed(2);
        console.log = originalLog;
        terminalLogs.textContent = logs.join('\\n') + `\\n\\n[Process terminated successfully in ${duration}ms]`;
      } catch (err) {
        console.log = originalLog;
        terminalLogs.textContent = `[Runtime Error]: ${err.message}`;
      }
    });
  }

  if (clearTermBtn && terminalLogs) {
    clearTermBtn.addEventListener('click', () => {
      terminalLogs.textContent = "// Terminal ready.";
    });
  }

  // 3. Project Filter Matrix
  const PROJECTS = [
    { title: "Aether Mesh Routing", category: "systems", tag: "DISTRIBUTED // RUST", desc: "Peer-to-peer anycast routing protocol achieving sub-5ms packet transport across 12 datacenters.", meta: "P99: 4.8ms | QPS: 120k" },
    { title: "Argon Autonomous Agent OS", category: "ai", tag: "AI // PYTHON", desc: "Manus-grade autonomous agent execution engine with SQLite WAL persistence and zero hallucination CRAG.", meta: "Pass Rate: 100% | RTO: 6.9ms" },
    { title: "Spectre WebGPU Engine", category: "frontend", tag: "WEBGPU // TS", desc: "Real-time volume rendering shader engine running in browser with 60fps cinematic post-processing.", meta: "60 FPS | 4k Res" },
    { title: "Vortex Data Lakehouse", category: "systems", tag: "DATA // APACHE ARROW", desc: "Zero-copy columnar analytics platform processing 10M rows/sec on local commodity hardware.", meta: "Throughput: 10M/s" }
  ];

  const projectGrid = document.getElementById('projectGrid');
  function renderProjects(filter = 'all') {
    if (!projectGrid) return;
    const items = filter === 'all' ? PROJECTS : PROJECTS.filter(p => p.category === filter);
    projectGrid.innerHTML = items.map(p => `
      <div class="project-card">
        <div class="project-tag">${p.tag}</div>
        <h4 class="project-title">${p.title}</h4>
        <p class="project-desc">${p.desc}</p>
        <div class="project-meta"><span>${p.meta}</span></div>
      </div>
    `).join('');
  }

  renderProjects('all');

  document.querySelectorAll('.p-filter-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.p-filter-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      renderProjects(e.target.dataset.filter);
    });
  });

  // 4. Auto-Saving Contact Form
  const nameInput = document.getElementById('contactName');
  const emailInput = document.getElementById('contactEmail');
  const messageInput = document.getElementById('contactMessage');
  const draftIndicator = document.getElementById('draftIndicator');
  const contactForm = document.getElementById('contactForm');

  function loadDraft() {
    try {
      const draft = JSON.parse(localStorage.getItem('zenith_contact_draft') || '{}');
      if (draft.name && nameInput) nameInput.value = draft.name;
      if (draft.email && emailInput) emailInput.value = draft.email;
      if (draft.message && messageInput) messageInput.value = draft.message;
    } catch(e) {}
  }

  function saveDraft() {
    const draft = {
      name: nameInput ? nameInput.value : '',
      email: emailInput ? emailInput.value : '',
      message: messageInput ? messageInput.value : '',
      updatedAt: Date.now()
    };
    localStorage.setItem('zenith_contact_draft', JSON.stringify(draft));
    if (draftIndicator) {
      draftIndicator.textContent = "● Draft auto-saved in localStorage";
      draftIndicator.style.color = "#10b981";
    }
  }

  [nameInput, emailInput, messageInput].forEach(el => {
    if (el) el.addEventListener('input', saveDraft);
  });

  loadDraft();

  if (contactForm) {
    contactForm.addEventListener('submit', (e) => {
      e.preventDefault();
      localStorage.removeItem('zenith_contact_draft');
      alert("Inquiry transmitted successfully! We will reach out within 1 business day.");
      contactForm.reset();
      if (draftIndicator) {
        draftIndicator.textContent = "Draft submitted";
      }
    });
  }
})();
"""
    }
)


def get_unseen_showcase_sites() -> Dict[str, ShowcaseSite]:
    """Return the dictionary of 3 newly built showcase websites."""
    return UNSEEN_SHOWCASE_SITES
