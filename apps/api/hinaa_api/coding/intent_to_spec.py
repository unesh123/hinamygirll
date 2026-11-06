"""Phase 20: Intent-to-Spec Compiler.

Converts free-form natural language prompts into explicit, typed, testable
functional specifications, data models, API route contracts, and design directives.
Supports English, Nepali (Devanagari), and Romanized Nepali inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DataField(BaseModel):
    name: str
    type: str  # text, integer, real, boolean, timestamp
    required: bool = True
    unique: bool = False
    default: Optional[Any] = None


class DataEntity(BaseModel):
    name: str
    description: str
    fields: List[DataField] = Field(default_factory=list)


class ApiRouteContract(BaseModel):
    method: str  # GET, POST, PUT, DELETE
    path: str
    description: str
    request_fields: List[str] = Field(default_factory=list)
    response_fields: List[str] = Field(default_factory=list)


class FeatureSpecification(BaseModel):
    spec_id: str
    title: str
    category: str
    tagline: str
    description: str
    prompt_text: str
    prompt_hash: str
    language_detected: str  # en-US, ne-NP, romanized-ne
    framework: str = "html_css_js"  # html_css_js, react_vite, fastapi_sqlite
    architecture_style: str = "fullstack_persisted"
    must_have_features: List[str] = Field(default_factory=list)
    nice_to_have_features: List[str] = Field(default_factory=list)
    data_entities: List[DataEntity] = Field(default_factory=list)
    api_routes: List[ApiRouteContract] = Field(default_factory=list)
    security_model: Dict[str, Any] = Field(default_factory=dict)
    design_system: Dict[str, Any] = Field(default_factory=dict)
    viewports: List[str] = Field(default_factory=lambda: ["desktop_1440", "tablet_768", "mobile_390"])
    is_from_catalog: bool = False
    compiled_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class IntentToSpecCompiler:
    """Compiles free-form user intents into production-grade project specifications."""

    def detect_language(self, prompt: str) -> str:
        """Detect whether prompt contains Devanagari Nepali, Romanized Nepali, or English."""
        # Devanagari unicode range: \u0900-\u097F
        devanagari_chars = len(re.findall(r"[\u0900-\u097F]", prompt))
        if devanagari_chars > 5:
            return "ne-NP"

        lower = prompt.lower()
        romanized_nepali_markers = ["sanchai", "kasto", "chha", "banaune", "garne", "nepal", "ru.", "npr", "hamro", "khata", "thangka", "pashmina"]
        if any(marker in lower for marker in romanized_nepali_markers):
            return "romanized-ne"

        return "en-US"

    def compile(self, prompt: str, requested_framework: Optional[str] = None) -> FeatureSpecification:
        """Compile prompt into an explicit, structured FeatureSpecification."""
        clean_prompt = prompt.strip()
        p_hash = hashlib.sha256(clean_prompt.encode("utf-8")).hexdigest()
        spec_id = f"spec-{p_hash[:10]}"
        lang = self.detect_language(clean_prompt)
        lower = clean_prompt.lower()

        # Domain classification
        if any(w in lower for w in ["appointment", "booking", "reservation", "clinic", "doctor", "dentist", "schedule", "अपोइन्टमेन्ट", "बुकिङ"]):
            category = "Appointment & Reservation Platform"
            title = "Bilingual Appointment & Reservation Platform"
            tagline = "Real-time reservation scheduling with collision prevention"
            description = "Full-stack appointment scheduling system with conflict detection, SQLite persistence, doctor slots, and role-based login."
            framework = requested_framework or "fastapi_sqlite"
            must_haves = [
                "Real reservation collision prevention (atomic slot locking)",
                "SQLite database persistence for appointments and doctor schedules",
                "Role-based authentication (Admin vs. Patient)",
                "Bilingual Nepali/English localization with dual toggle",
                "Responsive calendar and slot selection UI",
                "Integer NPR / USD pricing and receipt generation",
            ]
            entities = [
                DataEntity(
                    name="Appointment",
                    description="Individual patient booking slot",
                    fields=[
                        DataField(name="id", type="text", unique=True),
                        DataField(name="patient_name", type="text"),
                        DataField(name="doctor_name", type="text"),
                        DataField(name="slot_time", type="text"),
                        DataField(name="status", type="text", default="CONFIRMED"),
                        DataField(name="created_at", type="timestamp"),
                    ]
                ),
                DataEntity(
                    name="DoctorSchedule",
                    description="Doctor availability and slot capacity",
                    fields=[
                        DataField(name="doctor_id", type="text"),
                        DataField(name="doctor_name", type="text"),
                        DataField(name="available_slots", type="text"),
                        DataField(name="department", type="text"),
                    ]
                )
            ]
            api_routes = [
                ApiRouteContract(method="GET", path="/api/appointments", description="List all scheduled appointments", response_fields=["appointments"]),
                ApiRouteContract(method="POST", path="/api/appointments", description="Create new booking with collision check", request_fields=["patient_name", "doctor_name", "slot_time"], response_fields=["success", "appointment_id"]),
                ApiRouteContract(method="GET", path="/api/slots", description="Retrieve available slots for a given doctor", request_fields=["doctor_id"], response_fields=["slots"]),
            ]
            security = {
                "auth_type": "server_session",
                "password_hashing": "pbkdf2_hmac",
                "csrf_protection": True,
                "input_sanitization": True,
            }

        elif any(w in lower for w in ["civic", "telemetry", "dashboard", "environment", "pollution", "air quality", "water", "weather", "सेन्सर", "वातावरण"]):
            category = "Civic & Environmental Telemetry Dashboard"
            title = "Civic Telemetry & Environmental Intelligence Dashboard"
            tagline = "Verified public data feeds with interactive analytics and error recovery"
            description = "Civic monitoring dashboard tracking municipal telemetry, environmental sensors, air/water quality metrics, and source citations."
            framework = requested_framework or "html_css_js"
            must_haves = [
                "Public telemetry data visualizations with SVG charts",
                "Source provenance and citation badges for each metric",
                "Bilingual Nepali/English filterable regional views",
                "Dynamic time-window filters (24h, 7d, 30d)",
                "Error boundary and retry fallbacks for offline feeds",
                "WCAG 2.1 AA compliant color contrast and screen-reader tags",
            ]
            entities = [
                DataEntity(
                    name="TelemetryReading",
                    description="Sensor time-series measurement",
                    fields=[
                        DataField(name="station_id", type="text"),
                        DataField(name="parameter", type="text"),
                        DataField(name="value", type="real"),
                        DataField(name="unit", type="text"),
                        DataField(name="source_agency", type="text"),
                        DataField(name="timestamp", type="timestamp"),
                    ]
                )
            ]
            api_routes = [
                ApiRouteContract(method="GET", path="/api/telemetry/latest", description="Get latest readings across all stations", response_fields=["readings"]),
                ApiRouteContract(method="GET", path="/api/telemetry/history", description="Time-series historical trend for station", request_fields=["station_id", "range"], response_fields=["history"]),
            ]
            security = {
                "auth_type": "public_read_signed_write",
                "cors_policy": "restricted_origins",
                "rate_limiting": "60_req_per_min",
            }

        elif any(w in lower for w in ["khata", "inventory", "invoice", "accounting", "pos", "billing", "खाता", "बिल"]):
            category = "Business Accounting & Operations App"
            title = "Himalayan Khata & Invoicing Operations"
            tagline = "Integer NPR accounting, inventory tracking, and client ledger"
            description = "Small business operations app with inventory control, integer NPR ledger calculations, VAT/PAN support, and invoice generation."
            framework = requested_framework or "fastapi_sqlite"
            must_haves = [
                "Accurate integer NPR accounting (zero float rounding drift)",
                "SQLite ledger persistence across restarts",
                "Live stock and inventory count decrementing",
                "Printable/exportable tax invoices with PAN/VAT headers",
                "Customer outstanding balance ledger (उधारो / नगद)",
                "Searchable product catalog and quick billing keypad",
            ]
            entities = [
                DataEntity(
                    name="Invoice",
                    description="Customer transaction record",
                    fields=[
                        DataField(name="invoice_no", type="text", unique=True),
                        DataField(name="customer_name", type="text"),
                        DataField(name="total_npr", type="integer"),
                        DataField(name="vat_npr", type="integer"),
                        DataField(name="status", type="text", default="PAID"),
                        DataField(name="created_at", type="timestamp"),
                    ]
                ),
                DataEntity(
                    name="InventoryItem",
                    description="Stock item and unit cost",
                    fields=[
                        DataField(name="sku", type="text", unique=True),
                        DataField(name="title", type="text"),
                        DataField(name="unit_price_npr", type="integer"),
                        DataField(name="quantity", type="integer"),
                    ]
                )
            ]
            api_routes = [
                ApiRouteContract(method="GET", path="/api/invoices", description="List invoices with totals", response_fields=["invoices"]),
                ApiRouteContract(method="POST", path="/api/invoices", description="Create new invoice and update stock", request_fields=["customer_name", "items"], response_fields=["invoice_no", "total_npr"]),
                ApiRouteContract(method="GET", path="/api/inventory", description="Get inventory list", response_fields=["items"]),
            ]
            security = {
                "auth_type": "server_session",
                "db_integrity": "sqlite_foreign_keys_enabled",
                "financial_safety": "integer_paisa_arithmetic",
            }

        else:
            # General-purpose bespoke application
            words = [w.capitalize() for w in re.findall(r"\b[a-zA-Z]{3,}\b", clean_prompt)[:4]]
            app_title = " ".join(words) if words else "Dynamic Web Application"
            category = "Bespoke Web Application"
            title = app_title
            tagline = f"Tailored application built from natural language requirements: {clean_prompt[:60]}..."
            description = f"Autonomous project generated from prompt: '{clean_prompt}'. Features custom UI, data persistence, and interactive mechanics."
            framework = requested_framework or "html_css_js"
            must_haves = [
                f"Core user workflow: {clean_prompt[:50]}",
                "Responsive layout declaring desktop (1440), tablet (768), and mobile (390) viewports",
                "Persistent state handling",
                "WCAG 2.1 AA accessible semantics and keyboard focus states",
                "Design Critic audit compliance >= 90/100",
            ]
            entities = [
                DataEntity(
                    name="AppItem",
                    description="Primary application state item",
                    fields=[
                        DataField(name="id", type="text", unique=True),
                        DataField(name="title", type="text"),
                        DataField(name="data", type="text"),
                        DataField(name="created_at", type="timestamp"),
                    ]
                )
            ]
            api_routes = [
                ApiRouteContract(method="GET", path="/api/items", description="Retrieve app state items", response_fields=["items"]),
                ApiRouteContract(method="POST", path="/api/items", description="Save or update state item", request_fields=["title", "data"], response_fields=["success", "id"]),
            ]
            security = {
                "auth_type": "scoped_token",
                "sandbox_origin": "isolated_preview",
            }

        design = {
            "primary_color": "#6366f1",
            "background": "#0b0f19",
            "font_family": "Plus Jakarta Sans, sans-serif",
            "contrast_ratio": "7:1",
            "reduced_motion": True,
        }

        return FeatureSpecification(
            spec_id=spec_id,
            title=title,
            category=category,
            tagline=tagline,
            description=description,
            prompt_text=clean_prompt,
            prompt_hash=p_hash,
            language_detected=lang,
            framework=framework,
            must_have_features=must_haves,
            nice_to_have_features=["Subtle 60fps micro-animations", "Offline cached status pill"],
            data_entities=entities,
            api_routes=api_routes,
            security_model=security,
            design_system=design,
            is_from_catalog=False,
        )


_GLOBAL_COMPILER: Optional[IntentToSpecCompiler] = None


def get_intent_to_spec_compiler() -> IntentToSpecCompiler:
    global _GLOBAL_COMPILER
    if _GLOBAL_COMPILER is None:
        _GLOBAL_COMPILER = IntentToSpecCompiler()
    return _GLOBAL_COMPILER
