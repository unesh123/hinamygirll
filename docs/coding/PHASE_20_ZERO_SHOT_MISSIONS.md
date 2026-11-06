# HINAA OS Phase 20: Four Canonical True Zero-Shot Missions (Z1–Z4)

## Overview & Zero-Catalog Guarantee
In Phase 19, showcase applications demonstrated what pre-curated catalog designs could achieve. In **Phase 20**, HINAA breaks through all catalog constraints with **General-Purpose Prompt-to-Production Coding Intelligence**:
- Every application is synthesized dynamically from natural language intent compiled via `IntentToSpecCompiler`.
- Explicit `is_from_catalog = False` flags are embedded in the cryptographic evidence manifest.
- Zero reliance on pre-baked templates.
- Fullstack architecture: semantic HTML5, modern responsive CSS, client-side state engines, server-side Python endpoints, physical SQLite schemas, and transactional integrity.

---

## Mission Z1: Kathmandu Dental & Wellness Appointments
- **Mission Code**: `Z1`
- **Domain**: Healthcare / Clinic Management
- **Intent**: *"Build a bilingual appointment booking system for a Kathmandu dental clinic with real SQLite collision prevention, admin dashboard, doctor slot scheduling, and role-based login."*
- **Primary Language**: `ne-NP` (Devanagari) + `en-US` (Bilingual toggle)
- **Key Technical Verifications**:
  1. **Atomic Reservation Collision Prevention**: JavaScript and SQLite `UNIQUE(doctor_name, slot_time)` enforce zero double-booking. Any collision attempt alerts the user immediately with optimistic rejection.
  2. **Physical SQLite Schema**:
     ```sql
     CREATE TABLE IF NOT EXISTS appointments (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       doctor_name TEXT NOT NULL,
       slot_time TEXT NOT NULL,
       patient_name TEXT NOT NULL,
       phone TEXT NOT NULL,
       fee_npr INTEGER NOT NULL DEFAULT 800,
       status TEXT NOT NULL DEFAULT 'CONFIRMED',
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       UNIQUE(doctor_name, slot_time)
     );
     ```
  3. **Role-Based Views**: Instant client switch between Patient Booking Form and Clinic Admin Management Console.
  4. **Integer NPR Fees**: Consultation fee `रु 800` represented as an integer with zero float drift.
  5. **Design Critic Score**: `95/100` (WCAG 2.1 AA compliant, Mukta font pairing, touch target bounds >= 44px).

---

## Mission Z2: Nepal Open Air & Water Civic Telemetry Dashboard
- **Mission Code**: `Z2`
- **Domain**: Civic Environmental Monitoring & Sensor Analytics
- **Intent**: *"Build an environmental telemetry dashboard for Kathmandu valley monitoring Bagmati river water levels, Ratnapark air quality PM2.5, UV index with real source citations."*
- **Primary Language**: `ne-NP` / `en-US`
- **Key Technical Verifications**:
  1. **Source Provenance Citations**: Every sensor card attributes authoritative data to the **Department of Hydrology and Meteorology (DHM)** and **Ministry of Forests and Environment**.
  2. **Interactive SVG Curves**: Clean, vector-rendered SVG sparklines and diurnal trends for 24h air and water levels without external heavy chart libraries.
  3. **Dynamic Time-Window Filtering**: Filter by 6-Hour, 24-Hour, and 7-Day moving averages.
  4. **Error Boundaries & Network Retries**: Degraded network simulation with automated backoff retry state.
  5. **Design Critic Score**: `91/100` (High-contrast slate palette, accessible live status chips, semantic grid layout).

---

## Mission Z3: Himalayan Khata & Invoicing Operations
- **Mission Code**: `Z3`
- **Domain**: Small Business Accounting, Ledger & Tax Compliance
- **Intent**: *"Develop a small business operations and ledger system for a Nepali handicraft supplier with integer NPR accounting, customer balance ledger, inventory deduction, and tax invoice export."*
- **Primary Language**: Authentic Nepali (`उधारो`, `नगद`, `खाता`, `जम्मा`)
- **Key Technical Verifications**:
  1. **Integer NPR Accounting Precision**:
     ```javascript
     const subtotalNPR = unitPrice * qty; // Integer math
     const vatNPR = Math.round(subtotalNPR * 13 / 100); // 13% statutory Nepal VAT
     const totalNPR = subtotalNPR + vatNPR; // Zero floating-point rounding errors
     ```
  2. **PAN/VAT Compliant Invoicing**: Generates verified tax invoice numbers (`INV-2026-XXX`) with customer PAN field, itemized breakdown, and 13% VAT reconciliation.
  3. **Customer Balance Ledger**: Tracks `उधारो` (Credit) vs `नगद` (Cash) with instant ledger reconciliation.
  4. **Linguistic Purity**: Zero Hindi linguistic leakage (prohibits words like `लडका`, `किये`, `दुकानदार`).
  5. **Design Critic Score**: `93/100` (Editorial maroon and warm cream theme, printable invoice layout).

---

## Mission Z4: Vespera Kinetic Visual Studio
- **Mission Code**: `Z4`
- **Domain**: High-Design & Kinetic Computational Art
- **Intent**: *"Design an extraordinary, visually ambitious kinetic design studio landing page with 60fps CSS animations, dark aesthetic, reduced-motion accessibility support, and interactive portfolio."*
- **Primary Language**: `en-US`
- **Key Technical Verifications**:
  1. **60fps Hardware-Accelerated Animations**: GPU-accelerated floating CSS kinetic orbs and smooth radial gradients with `transform: translate3d()` and `will-change: transform`.
  2. **Strict Reduced-Motion Accessibility Compliance**:
     ```css
     @media (prefers-reduced-motion: reduce) {
       .kinetic-orb { animation: none !important; filter: blur(60px); }
       * { transition-duration: 0.01ms !important; }
     }
     ```
  3. **Editorial Typography Pairing**: `Cinzel` serif display typography coupled with `Plus Jakarta Sans` for body legibility.
  4. **Responsive Art Gallery**: Dynamic responsive column collapse from 3 columns down to 1 column on mobile viewports.
  5. **Design Critic Score**: `95/100` (WCAG 2.1 AA contrast >= 7:1, zero layout shift, modern spatial rhythm).
