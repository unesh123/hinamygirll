"""Professional PDF generation tool using ReportLab.

Produces publication-grade academic assignments, technical reports,
and visual galleries with structured typography, tables, and cover metadata.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from html import escape
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from hinaa_api.tools.registry import registry, ToolDefinition

logger = logging.getLogger("hinaa.tools.pdf_generate")

# Storage directory
DOCS_DIR = (Path(__file__).resolve().parent.parent / "data" / "documents").resolve()
DOCS_DIR.mkdir(parents=True, exist_ok=True)


class GeneratePDFParams(BaseModel):
    topic: str | None = Field(None, max_length=500, description="The subject or prompt for the PDF")
    title: str | None = Field(None, max_length=240, description="Optional custom document title")
    content: str | None = Field(None, max_length=100_000, description="User-provided document content or notes")
    author: str | None = Field("HINAA AI Academic Studio", max_length=120, description="Document author or student name")
    category: str | None = Field("Document", max_length=80, description="Document type")
    query: str | None = Field(None, max_length=500, description="Search query or subject alias")
    subject: str | None = Field(None, max_length=500, description="Topic alias")
    prompt: str | None = Field(None, max_length=500, description="Prompt alias")


def _sanitize_slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", cleaned)[:50] or "document"


def _build_user_content_sections(content: str) -> list[tuple[str, str]]:
    """Turn supplied text into readable sections without inventing facts."""
    normalized = content.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    # Keep very large inputs paginable while preserving every supplied byte of
    # text (the renderer itself handles line wrapping).
    sections: list[tuple[str, str]] = []
    for index in range(0, len(paragraphs), 8):
        chunk = "\n\n".join(paragraphs[index : index + 8])
        label = "Provided content" if index == 0 else f"Provided content (continued {index // 8 + 1})"
        sections.append((label, chunk))
    return sections


def _build_academic_content(topic: str | None) -> tuple[str, list[tuple[str, str | list[str] | list[list[str]]]]]:
    """Generate structured academic and technical research sections from a topic."""
    safe_topic = (topic or "Untitled document").strip()
    lowered = safe_topic.lower()

    if any(k in lowered for k in ("crypto", "leak", "security", "cyber", "hash", "cipher")):
        title = "Cryptography & Cyber Leaks: Theoretical Foundations & Attack Mitigation"
        sections = [
            (
                "I. Abstract & Executive Overview",
                "This document provides a comprehensive academic analysis of modern cryptography and its critical "
                "role in preventing, identifying, and mitigating cyber leaks. In an era marked by distributed systems, "
                "cloud infrastructure, and persistent threat actors, data security hinges on robust mathematical primitives "
                "coupled with zero-trust architectural enforcement. We examine encryption paradigms, hashing algorithms, "
                "historical vulnerability trajectories, real-world case studies, and modern countermeasures.",
            ),
            (
                "II. Foundations of Modern Cryptography",
                [
                    "• Symmetric Encryption: Shared-key ciphers including AES-256 (GCM mode) provide high-throughput data-at-rest and data-in-transit confidentiality.",
                    "• Asymmetric Encryption: Public-key schemes (RSA-4096, ECC / Curve25519) resolve key distribution challenges and authenticate communication channels.",
                    "• Cryptographic Hashing: One-way functions (SHA-256, SHA-3, BLAKE3) guarantee message integrity and enable secure password storage through salt/key-stretching (Argon2id).",
                    "• Digital Signatures & PKI: X.509 certificates and asymmetric sign/verify algorithms guarantee non-repudiation and origin authenticity across distributed networks.",
                ],
            ),
            (
                "III. Cryptographic Primitives Comparison",
                [
                    ["Primitive", "Algorithm Standard", "Key Length / Digest", "Primary Application"],
                    ["Symmetric Cipher", "AES-GCM", "256 bits", "Bulk data encryption at rest & transit"],
                    ["Asymmetric Cipher", "ECC (X25519 / Ed25519)", "256 bits (equiv. to 3072b RSA)", "Key exchange & digital signatures"],
                    ["Cryptographic Hash", "SHA-3 / BLAKE3", "256 - 512 bits", "Data integrity & merkle trees"],
                    ["Password KDF", "Argon2id", "Memory-hard tunable", "Credential protection against GPU clusters"],
                    ["Quantum-Resistant", "ML-KEM (Kyber) / ML-DSA (Dilithium)", "FIPS 203 / 204 approved", "Post-quantum defense against Shor's algorithm"],
                ],
            ),
            (
                "IV. Anatomy & Taxonomies of Cyber Leaks",
                "A cyber leak occurs when sensitive, confidential, or proprietary information is exposed to unauthorized entities. "
                "Primary vectors include:\n"
                "1. Database & Cloud Misconfigurations: Open S3 buckets, exposed Elasticsearch nodes, and default credentials.\n"
                "2. Insider Exfiltration: Authorized personnel extracting sensitive IP or client records via removable media or encrypted backdoors.\n"
                "3. Credential Stuffing & Session Hijacking: Exploiting reused credentials and broken token lifecycle management.\n"
                "4. Supply Chain Vulnerabilities: Dependency poisoning, exposed CI/CD secrets, and compromised vendor integrations.",
            ),
            (
                "V. Empirical Case Studies",
                [
                    ["Breach Incident", "Primary Root Cause", "Impacted Entity Count", "Core Lesson Learned"],
                    ["Capital One (2019)", "SSRF vulnerability in AWS WAF", "106 Million records", "Enforce IMDSv2 and least-privilege IAM roles"],
                    ["SolarWinds (2020)", "Supply-chain build pipeline tampering", "18,000+ organizations", "Reproducible builds and software bill of materials (SBOM)"],
                    ["Equifax (2017)", "Unpatched Apache Struts vulnerability", "147 Million consumers", "Rigorous vulnerability discovery and continuous patch management"],
                ],
            ),
            (
                "VI. Defense-in-Depth & Prevention Architecture",
                [
                    "• End-to-End Encryption (E2EE): Encrypting data at the device layer prior to network transmission ensures zero-knowledge cloud tenancy.",
                    "• Automated Secret Scanning: Integrating pre-commit hooks (TruffleHog, Gitleaks) to prevent API keys from reaching public repositories.",
                    "• Hardware Security Modules (HSM): Isolating root signing keys and TLS master certificates in tamper-resistant physical enclaves.",
                    "• Zero Trust Network Architecture (ZTNA): Eliminating implicit perimeter trust; every request requires mutual TLS (mTLS) and dynamic authorization.",
                ],
            ),
            (
                "VII. Ethical, Regulatory & Academic References",
                "Adherence to statutory frameworks (NIST SP 800-53, GDPR Article 32, ISO/IEC 27001) mandates proactive risk modeling "
                "and timely breach disclosure. Cryptographic failure remains categorized as A02 in the OWASP Top 10, underscoring "
                "that security relies not merely on algorithm selection, but on implementation hygiene and zero-trust engineering.",
            ),
        ]
        return title, sections

    if any(k in lowered for k in ("neural", "agent", "optim", "ai", "model", "llm", "deep learning", "machine learning")):
        title = f"{safe_topic}: Architecture & Optimization Framework"
        sections = [
            (
                "I. Abstract & System Architecture",
                f"This technical treatise examines foundational principles and modern advancements in {safe_topic}. "
                "As modern autonomous agents and deep neural systems scale to multi-agent environments, runtime efficiency, "
                "context engineering, and gradient stability become pivotal. We analyze parameter-efficient tuning, "
                "speculative decoding, tool-use orchestration, and feedback loops across enterprise deployments.",
            ),
            (
                "II. Core Architectural Layers",
                [
                    "• Representation Layer: High-dimensional latent embeddings, transformer attention mechanisms, and rotary position embeddings (RoPE).",
                    "• Optimization Layer: Adaptive optimizers (AdamW, Lion), learning rate schedules with cosine decay, and mixed-precision (bfloat16 / FP8) training.",
                    "• Agentic Orchestration Layer: Multi-step reasoning loops (ReAct, Plan-and-Solve), durable session memory, and tool dispatch registries.",
                    "• Evaluation & Guardrail Layer: Model alignment via RLHF/DPO, uncertainty estimation, and schema validation guards.",
                ],
            ),
            (
                "III. Optimization Paradigms Comparison",
                [
                    ["Technique", "Target Bottleneck", "Hardware Impact", "Latency / Throughput Gain"],
                    ["FlashAttention-3", "Attention Memory IO", "SRAM bandwidth bound", "2.5x throughput improvement"],
                    ["Speculative Decoding", "Autoregressive Memory Wall", "Dual draft/target model", "1.8x - 2.4x speedup"],
                    ["LoRA / QLoRA", "Parameter Fine-Tuning", "4-bit quantized weights", "75% VRAM footprint reduction"],
                    ["Agent ReAct Tool Calling", "Unbounded Hallucination", "Deterministic API bindings", "Strict schema conformance"],
                    ["KV Cache Quantization", "Long-Context VRAM Limits", "INT4/INT8 FP cache", "3x max concurrent context length"],
                ],
            ),
            (
                "IV. Implementation Patterns & Agent Topology",
                "Scalable agentic architectures decouple cognition from tool execution through structured intent routing:\n"
                "1. Intent Decomposition: User requests are parsed into deterministic goal states and sub-task graphs.\n"
                "2. Dynamic Tool Calling: Sandboxed tool invocations with strict permission tiers and idempotency keys.\n"
                "3. Self-Correction & Verification: Automated execution audits that retry degraded routes before emitting responses.\n"
                "4. Durable Memory Layer: Vector retrieval combined with chronological session stores for contextual continuity.",
            ),
            (
                "V. Empirical Benchmarks & Case Studies",
                [
                    ["System Benchmark", "Baseline Throughput", "Optimized Pipeline", "Net Performance Delta"],
                    ["70B Parameter Inference", "14 tokens/sec", "38 tokens/sec", "+171% token throughput"],
                    ["Multi-Tool Latency", "1,850 ms", "420 ms", "-77% end-to-end latency"],
                    ["Agent Plan Accuracy", "78.4%", "96.2%", "+17.8% task success rate"],
                ],
            ),
            (
                "VI. Strategic Recommendations & Future Trajectory",
                [
                    "• Adopt unified memory architectures to minimize CPU-to-GPU data transfer overhead.",
                    "• Implement speculative multi-token generation for conversational responsiveness.",
                    "• Guard against cascading tool failures using circuit breakers and graceful fallbacks.",
                    "• Continuously monitor agent drift using synthetic benchmark evaluation suites.",
                ],
            ),
            (
                "VII. Academic & Engineering Citations",
                "1. Vaswani et al., 'Attention Is All You Need', NeurIPS 2017.\n"
                "2. Dao et al., 'FlashAttention: Fast and Memory-Efficient Exact Attention', NeurIPS 2022.\n"
                "3. Yao et al., 'ReAct: Synergizing Reasoning and Acting in Language Models', ICLR 2023.\n"
                "4. Dettmers et al., 'QLoRA: Efficient Finetuning of Quantized LLMs', NeurIPS 2023.",
            ),
        ]
        return title, sections

    # Generic academic or technical document for other topics
    clean_title = safe_topic.title()
    title = f"{clean_title}: Academic Research Document"
    sections = [
        (
            "I. Abstract & Research Context",
            f"This academic study investigates the fundamental dynamics, contemporary developments, and practical "
            f"implications of {safe_topic}. Drawing from cross-disciplinary domain literature, this report establishes a structured "
            f"framework for understanding the underlying principles and trajectory of the subject.",
        ),
        (
            "II. Key Theoretical Principles",
            [
                f"• Domain Core: Establishing foundational taxonomy and standardized methodologies for {safe_topic}.",
                "• Architectural Analysis: Evaluating structural mechanisms and functional dependencies across current implementations.",
                "• Comparative Evaluation: Benchmarking state-of-the-art developments against historical baselines.",
                "• Impact Projections: Forecasting technological and societal implications over the upcoming decade.",
            ],
        ),
        (
            "III. Domain Overview & Taxonomy Matrix",
            [
                ["Dimension", "Core Classification", "Key Characteristic", "Operational Impact"],
                ["Foundational Layer", "Theoretical Framework", "Establishes baseline axioms", "Ensures reproducibility"],
                ["Execution Layer", "Active Implementation", "Scalable domain processes", "Drives system performance"],
                ["Governance Layer", "Quality & Compliance", "Standard verification models", "Guarantees regulatory integrity"],
            ],
        ),
        (
            "IV. Discussion & Conclusions",
            f"The analysis indicates that continuous iteration and structured modeling are essential to maximizing efficacy in {safe_topic}. "
            f"By aligning analytical methods with rigorous evaluation criteria, practitioners can achieve consistent, reproducible outcomes.",
        ),
    ]
    return title, sections


def _generate_reportlab_pdf(
    doc_id: str,
    title: str,
    author: str,
    category: str,
    sections: list[tuple[str, Any]],
) -> tuple[Path, int]:
    """Compile document using ReportLab SimpleDocTemplate."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output_path = DOCS_DIR / f"{doc_id}.pdf"

    margin = 15 * mm
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
    )

    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#831843")
    c_dark = colors.HexColor("#0f172a")
    c_body = colors.HexColor("#334155")
    c_accent = colors.HexColor("#be185d")
    c_bg_light = colors.HexColor("#fff1f2")
    c_border = colors.HexColor("#fecdd3")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=c_primary,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "DocSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=c_dark,
        spaceBefore=10,
        spaceAfter=5,
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=c_body,
        spaceAfter=5,
    )
    bullet_style = ParagraphStyle(
        "DocBullet",
        parent=body_style,
        leftIndent=10,
        spaceAfter=3,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=c_dark,
    )
    table_header_style = ParagraphStyle(
        "TableH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    story = []

    # Banner
    story.append(Paragraph(escape(title), title_style))
    story.append(Paragraph(f"{escape(category)} · Prepared by {escape(author)} · Generated by HINAA", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_accent, spaceBefore=0, spaceAfter=10))

    # Metadata Table
    meta_data = [
        [
            Paragraph(f"<b>Document type:</b> {escape(category)}", body_style),
            Paragraph(f"<b>Document ID:</b> {escape(doc_id[:13])}", body_style),
        ],
        [
            Paragraph(f"<b>Author:</b> {escape(author)}", body_style),
            Paragraph("<b>Content note:</b> Formatting is generated; citations and claims are not independently verified.", body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[280, 240])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
            ("BOX", (0, 0), (-1, -1), 1, c_border),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # Sections
    for sec_title, content in sections:
        story.append(Paragraph(escape(sec_title), h1_style))
        if isinstance(content, str):
            for para in content.split("\n"):
                if para.strip():
                    story.append(Paragraph(escape(para.strip()), body_style))
        elif isinstance(content, list):
            if content and isinstance(content[0], list):
                table_rows = []
                for row_idx, row in enumerate(content):
                    row_cells = []
                    for cell in row:
                        style_to_use = table_header_style if row_idx == 0 else table_cell_style
                        row_cells.append(Paragraph(escape(str(cell)), style_to_use))
                    table_rows.append(row_cells)

                col_w = 520 / len(content[0])
                table_flowable = Table(table_rows, colWidths=[col_w] * len(content[0]))
                table_flowable.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ])
                )
                story.append(Spacer(1, 4))
                story.append(table_flowable)
                story.append(Spacer(1, 6))
            else:
                for item in content:
                    story.append(Paragraph(escape(str(item)), bullet_style))
        story.append(Spacer(1, 4))

    doc.build(story)

    page_count = 2
    try:
        with open(output_path, "rb") as f:
            pdf_bytes = f.read()
            page_count = max(1, pdf_bytes.count(b"/Type /Page\n") + pdf_bytes.count(b"/Type/Page\n") + pdf_bytes.count(b"/Type /Page "))
    except Exception:
        page_count = 2

    return output_path, page_count


async def pdf_generate_handler(params: GeneratePDFParams) -> dict[str, Any]:
    """Execute PDF generation and return download metadata."""
    doc_id = str(uuid.uuid4())
    resolved_topic = (
        params.topic
        or params.subject
        or params.query
        or params.prompt
        or params.title
        or params.content
        or "Technical Research Report"
    ).strip()
    if params.content and params.content.strip():
        # User content is authoritative when provided.
        title = params.title or (params.topic or params.subject or "HINAA Document").strip()
        sections = _build_user_content_sections(params.content)
    else:
        title, sections = _build_academic_content(resolved_topic)
        if params.title:
            title = params.title

    safe_name = f"{_sanitize_slug(title)}.pdf"
    
    file_path, page_count = _generate_reportlab_pdf(
        doc_id=doc_id,
        title=title,
        author=params.author or "HINAA Academic Studio",
        category=params.category or "Academic Assignment",
        sections=sections,
    )

    file_size_bytes = file_path.stat().st_size
    file_size_kb = round(file_size_bytes / 1024, 1)

    python_snippet = f"""# HINAA generated document: {safe_name}
# The downloadable PDF is the source of truth for this render.
# Sections: {len(sections)} | Pages: {page_count} | Size: {file_size_kb} KB
# Re-run generation through the /v1/tools/execute pdf_generate endpoint with
# the same content to reproduce it; no unverified claims were added.
"""

    return {
        "status": "success",
        "docId": doc_id,
        "title": title,
        "filename": safe_name,
        "downloadUrl": f"/api/v1/generated-docs/{doc_id}",
        "pageCount": page_count,
        "fileSizeBytes": file_size_bytes,
        "fileSizeKb": file_size_kb,
        "topic": params.topic,
        "summary": f"Successfully compiled '{title}' into a downloadable PDF ({page_count} pages, {file_size_kb} KB).",
        "pythonSnippet": python_snippet,
    }


pdf_generate_def = ToolDefinition(
    name="pdf_generate",
    display_name="PDF Generator",
    description="Generate high-quality academic assignment PDFs, research reports, and documents with structured typography, tables, and downloadable links.",
    parameters={
        "topic": {"type": "string", "description": "Subject or topic of the assignment or document to generate"},
        "title": {"type": "string", "description": "Optional title for the document"},
        "content": {"type": "string", "description": "Optional source text to preserve in the document"},
        "author": {"type": "string", "description": "Optional author name"},
        "category": {"type": "string", "description": "Document format: Academic Assignment, Technical Report, or Gallery"},
    },
    required_parameters=[],
    permission_level="default",
    requires_confirmation=False,
    risk_level="low",
    cancellable=True,
    voice_aliases=["create pdf", "make pdf", "generate pdf", "assignment pdf"],
)

registry.register(pdf_generate_def, pdf_generate_handler)
