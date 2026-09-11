from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class CapabilityStatus(str, Enum):
    UNCONFIGURED = "unconfigured"
    CONFIGURED = "configured"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    VERIFYING = "verifying"


class RiskLevel(str, Enum):
    READ = "read"
    LOW_MUTATION = "low-mutation"
    EXTERNAL_MUTATION = "external-mutation"
    HIGH_IMPACT = "high-impact"


class ApprovalPolicy(str, Enum):
    AUTOMATIC = "automatic"
    SESSION_CONSENT = "session-consent"
    ALWAYS_CONFIRM = "always-confirm"
    PROHIBITED = "prohibited"


class ExecutionLocation(str, Enum):
    BROWSER = "browser"
    API = "api"
    WORKER = "worker"
    DESKTOP_BRIDGE = "desktop_bridge"
    EXTERNAL_PROVIDER = "external_provider"


@dataclass(frozen=True)
class CommandDefinition:
    version: int = 1
    name: str = ""
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    examples: list[str] = field(default_factory=list)
    inputSchema: dict[str, Any] = field(default_factory=dict)
    capability: str = ""
    riskLevel: RiskLevel = RiskLevel.READ
    approvalPolicy: ApprovalPolicy = ApprovalPolicy.AUTOMATIC
    availability: CapabilityStatus = CapabilityStatus.UNCONFIGURED
    executionLocation: ExecutionLocation = ExecutionLocation.API
    requiresAuth: bool = False
    descriptionShort: str = ""


# Initial registered commands
COMMAND_REGISTRY: dict[str, CommandDefinition] = {
    "search": CommandDefinition(
        name="search",
        aliases=["search", "find", "lookup"],
        description="Search the live web for current information with cited sources",
        examples=[
            "/search latest official Vite PWA documentation",
            "/search current anime streaming services",
            "/search React 19 release date",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "count": {"type": "integer", "description": "Result count (1-20)", "default": 5, "minimum": 1, "maximum": 20},
                "freshness": {"type": "string", "description": "Recency filter: day, week, month, year, or YYYY-MM-DD..YYYY-MM-DD"},
                "includeDomains": {"type": "array", "items": {"type": "string"}, "description": "Strict source-domain allowlist"},
                "excludeDomains": {"type": "array", "items": {"type": "string"}, "description": "Source-domain blocklist"},
            },
            "required": ["query"],
        },
        capability="web_search",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.SESSION_CONSENT,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Web search with citations",
    ),
    "research": CommandDefinition(
        name="research",
        aliases=["research", "investigate", "deep research"],
        description="Multi-step cited research with configurable depth",
        examples=[
            "/research current VRM lip-sync techniques",
            "/research compare Python async frameworks",
            "/research latest AI agent architectures effort=deep",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The research question"},
                "effort": {"type": "string", "enum": ["lite", "standard", "deep", "exhaustive", "frontier"], "default": "lite"},
                "background": {"type": "boolean", "description": "Run as background task (required for frontier)", "default": False},
                "includeDomains": {"type": "array", "items": {"type": "string"}},
                "excludeDomains": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
        capability="web_research",
        riskLevel=RiskLevel.LOW_MUTATION,
        approvalPolicy=ApprovalPolicy.ALWAYS_CONFIRM,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Deep cited research",
    ),
    "answer": CommandDefinition(
        name="answer",
        aliases=["answer", "verify", "answer with sources"],
        description="Get a concise cited answer to a factual question",
        examples=[
            "/answer What is the current Python version?",
            "/answer latest React 19 features",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The factual question"},
                "freshness": {"type": "string"},
            },
            "required": ["query"],
        },
        capability="web_answer",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.SESSION_CONSENT,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Cited factual answer",
    ),
    "extract": CommandDefinition(
        name="extract",
        aliases=["extract", "read", "read page"],
        description="Extract clean markdown from up to 5 public URLs",
        examples=[
            "/extract https://example.com/article",
            "/extract https://a.com https://b.com",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "maxAge": {"type": "integer", "description": "Max cached age in seconds"},
            },
            "required": ["urls"],
        },
        capability="web_extract",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.SESSION_CONSENT,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Read public pages",
    ),
    "image_search": CommandDefinition(
        name="image_search",
        aliases=["image search", "find images"],
        description="Find public web images (requires You.com beta access)",
        examples=[
            "/image_search sakura anime wallpaper",
            "/image_search Vite logo transparent",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Image search query"},
                "count": {"type": "integer", "default": 6, "minimum": 1, "maximum": 12},
            },
            "required": ["query"],
        },
        capability="image_search",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.SESSION_CONSENT,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Find public images",
    ),
    "image": CommandDefinition(
        name="image",
        aliases=["image", "draw", "generate", "imagine", "img", "pic", "image_generate"],
        description="Generate AI images via local ComfyUI, Freepik/Magnific, or cloud models (Flux, Anime, Realism)",
        examples=[
            "/image a cyberpunk cityscape at sunset",
            "/image sakura companion in anime style --model=flux-anime --seed=42",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Positive prompt"},
                "model": {"type": "string", "description": "Image model: flux, flux-anime, flux-realism, flux-3d, turbo", "default": "flux"},
                "seed": {"type": "integer", "description": "Seed for deterministic generation"},
                "count": {"type": "integer", "default": 1, "minimum": 1, "maximum": 10},
                "mode": {"type": "string", "enum": ["fast", "quality", "ultra"], "default": "fast"},
            },
            "required": ["prompt"],
        },
        capability="image_generation",
        riskLevel=RiskLevel.LOW_MUTATION,
        approvalPolicy=ApprovalPolicy.ALWAYS_CONFIRM,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Generate AI images",
    ),
    "image_generate": CommandDefinition(
        name="image_generate",
        aliases=["generate image", "create image", "draw", "imagine"],
        description="Generate images via local ComfyUI or cloud fallback",
        examples=[
            "/image_generate a cyberpunk cityscape at sunset",
            "/image_generate sakura companion --mode=quality --count=4",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Positive prompt"},
                "negative_prompt": {"type": "string", "default": ""},
                "count": {"type": "integer", "default": 1, "minimum": 1, "maximum": 10},
                "mode": {"type": "string", "enum": ["fast", "quality", "ultra"], "default": "fast"},
                "seed": {"type": "integer"},
            },
            "required": ["prompt"],
        },
        capability="image_generation",
        riskLevel=RiskLevel.LOW_MUTATION,
        approvalPolicy=ApprovalPolicy.ALWAYS_CONFIRM,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Generate AI images",
    ),
    "document": CommandDefinition(
        name="document",
        aliases=["document", "create doc", "write doc"],
        description="Create a document (PDF, DOCX, Markdown) from provided content",
        examples=[
            "/document create a report from @research-results",
            "/document write a summary of the meeting notes",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "format": {"type": "string", "enum": ["pdf", "docx", "markdown", "txt"], "default": "pdf"},
                "sources": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "content"],
        },
        capability="document_generation",
        riskLevel=RiskLevel.LOW_MUTATION,
        approvalPolicy=ApprovalPolicy.ALWAYS_CONFIRM,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Create documents",
    ),
    "pdf": CommandDefinition(
        name="pdf",
        aliases=["pdf", "create pdf", "export pdf"],
        description="Generate a PDF document from content or context references",
        examples=[
            "/pdf create a report from @research-results",
            "/pdf export the conversation as PDF",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "content"],
        },
        capability="pdf_generation",
        riskLevel=RiskLevel.LOW_MUTATION,
        approvalPolicy=ApprovalPolicy.ALWAYS_CONFIRM,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Create PDF documents",
    ),
    "presentation": CommandDefinition(
        name="presentation",
        aliases=["presentation", "slides", "create slides"],
        description="Create a presentation (PPTX) from content or research",
        examples=[
            "/presentation create slides from @research-results",
            "/presentation pitch deck for my startup idea",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "slides": {"type": "integer", "default": 10},
                "theme": {"type": "string", "default": "default"},
            },
            "required": ["title", "content"],
        },
        capability="presentation_generation",
        riskLevel=RiskLevel.LOW_MUTATION,
        approvalPolicy=ApprovalPolicy.ALWAYS_CONFIRM,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Create presentations",
    ),
    "analyze": CommandDefinition(
        name="analyze",
        aliases=["analyze", "analyze this", "review"],
        description="Analyze text, code, or files for issues, improvements, or insights",
        examples=[
            "/analyze this code for bugs",
            "/analyze @my-file.py for performance",
            "/analyze the conversation for action items",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "What to analyze (text, @reference, or context)"},
                "focus": {"type": "string", "enum": ["bugs", "performance", "security", "style", "summary"], "default": "summary"},
            },
            "required": ["target"],
        },
        capability="analysis",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.AUTOMATIC,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Analyze content",
    ),
    "summarize": CommandDefinition(
        name="summarize",
        aliases=["summarize", "summary", "tldr"],
        description="Summarize long content, conversations, or documents",
        examples=[
            "/summarize @long-document.pdf",
            "/summarize the last 10 messages",
            "/summarize @research-results key findings",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "What to summarize"},
                "length": {"type": "string", "enum": ["brief", "standard", "detailed"], "default": "standard"},
            },
            "required": ["target"],
        },
        capability="summarization",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.AUTOMATIC,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Summarize content",
    ),
    "plan": CommandDefinition(
        name="plan",
        aliases=["plan", "create plan", "make plan"],
        description="Create a structured plan or task breakdown",
        examples=[
            "/plan build a React dashboard with authentication",
            "/plan weekly content calendar for tech blog",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "The goal or project to plan"},
                "horizon": {"type": "string", "enum": ["day", "week", "month", "quarter"], "default": "week"},
            },
            "required": ["goal"],
        },
        capability="planning",
        riskLevel=RiskLevel.LOW_MUTATION,
        approvalPolicy=ApprovalPolicy.ALWAYS_CONFIRM,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Create plans",
    ),
    "play": CommandDefinition(
        name="play",
        aliases=["play", "music", "play music"],
        description="Search and play music via YouTube",
        examples=[
            "/play Sayaara",
            "/play latest lofi beats",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Music search query"},
            },
            "required": ["query"],
        },
        capability="media_playback",
        riskLevel=RiskLevel.EXTERNAL_MUTATION,
        approvalPolicy=ApprovalPolicy.ALWAYS_CONFIRM,
        executionLocation=ExecutionLocation.BROWSER,
        descriptionShort="Play music",
    ),
    "memory": CommandDefinition(
        name="memory",
        aliases=["memory", "remember", "recall"],
        description="Save or recall memories",
        examples=[
            "/memory save my preferred voice is natural",
            "/memory recall my project preferences",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["save", "recall", "list", "delete"]},
                "content": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["action"],
        },
        capability="memory",
        riskLevel=RiskLevel.LOW_MUTATION,
        approvalPolicy=ApprovalPolicy.SESSION_CONSENT,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Manage memories",
    ),
    "files": CommandDefinition(
        name="files",
        aliases=["files", "search files", "find files"],
        description="Search and manage local project files",
        examples=[
            "/files find all TypeScript configs",
            "/files list project assets",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "path": {"type": "string"},
            },
            "required": ["query"],
        },
        capability="file_search",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.AUTOMATIC,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Search files",
    ),
    "model": CommandDefinition(
        name="model",
        aliases=["model", "switch model", "change brain"],
        description="Switch the active brain model",
        examples=[
            "/model gpt-5.6-sol",
            "/model gemini-3.1-flash",
            "/model list",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "Model ID or 'list'"},
            },
            "required": ["model"],
        },
        capability="model_selection",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.AUTOMATIC,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Switch models",
    ),
    "voice": CommandDefinition(
        name="voice",
        aliases=["voice", "tts", "speak"],
        description="Configure voice settings or test TTS",
        examples=[
            "/voice test ElevenLabs",
            "/voice calibrate natural",
            "/voice list voices",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["test", "calibrate", "list", "set"]},
                "provider": {"type": "string"},
                "calibration": {"type": "string", "enum": ["natural", "soft", "lively"]},
            },
            "required": ["action"],
        },
        capability="voice_config",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.AUTOMATIC,
        executionLocation=ExecutionLocation.API,
        descriptionShort="Voice settings",
    ),
    "avatar": CommandDefinition(
        name="avatar",
        aliases=["avatar", "vrm", "model3d"],
        description="Configure 3D avatar settings",
        examples=[
            "/avatar switch hinaa-classic",
            "/avatar mode portrait",
            "/avatar tracking on",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["switch", "mode", "tracking", "import"]},
                "model": {"type": "string"},
                "mode": {"type": "string", "enum": ["portrait", "upperbody", "full"]},
            },
            "required": ["action"],
        },
        capability="avatar_config",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.AUTOMATIC,
        executionLocation=ExecutionLocation.BROWSER,
        descriptionShort="Avatar settings",
    ),
    "settings": CommandDefinition(
        name="settings",
        aliases=["settings", "config", "preferences"],
        description="Open or modify settings",
        examples=[
            "/settings open",
            "/settings language hi-IN",
            "/settings provider openai",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "section": {"type": "string"},
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["section"],
        },
        capability="settings",
        riskLevel=RiskLevel.READ,
        approvalPolicy=ApprovalPolicy.AUTOMATIC,
        executionLocation=ExecutionLocation.BROWSER,
        descriptionShort="Open settings",
    ),
    "automate": CommandDefinition(
        name="automate",
        aliases=["automate", "automation", "schedule"],
        description="Create or manage automated tasks",
        examples=[
            "/automate daily summary at 9am",
            "/automate weekly research on AI news",
        ],
        inputSchema={
            "type": "object",
            "properties": {
                "schedule": {"type": "string", "description": "Cron expression or natural language"},
                "task": {"type": "string", "description": "What to automate"},
                "tools": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["schedule", "task"],
        },
        capability="automation",
        riskLevel=RiskLevel.HIGH_IMPACT,
        approvalPolicy=ApprovalPolicy.ALWAYS_CONFIRM,
        executionLocation=ExecutionLocation.WORKER,
        descriptionShort="Manage automation",
    ),
}


def get_command(name: str) -> CommandDefinition | None:
    """Get a command by name or alias."""
    name = name.lower().strip()
    for cmd in COMMAND_REGISTRY.values():
        if cmd.name == name or name in cmd.aliases:
            return cmd
    return None


def list_commands() -> list[CommandDefinition]:
    """List all registered commands."""
    return list(COMMAND_REGISTRY.values())


def get_commands_by_capability(capability: str) -> list[CommandDefinition]:
    """Get commands that require a specific capability."""
    return [cmd for cmd in COMMAND_REGISTRY.values() if cmd.capability == capability]


# Context reference types for @ mentions
CONTEXT_TYPES = [
    "project",
    "file",
    "folder",
    "conversation",
    "memory",
    "task",
    "artifact",
    "tool",
    "browser_page",
    "selected_text",
]


@dataclass(frozen=True)
class ContextReference:
    version: int = 1
    id: str = ""
    kind: str = ""
    sourceId: str = ""
    label: str = ""
    access: Literal["read", "use", "execute"] = "read"
    sourceVersion: str | None = None


@dataclass(frozen=True)
class AttachmentReference:
    version: int = 1
    id: str = ""
    filename: str = ""
    mimeType: str = ""
    byteSize: int = 0


@dataclass(frozen=True)
class CommandInvocation:
    version: int = 1
    invocationId: str = ""
    commandName: str = ""
    rawArguments: str = ""
    parsedArguments: dict[str, Any] = field(default_factory=dict)
    source: Literal["slash", "mention-alias", "voice"] = "slash"


@dataclass(frozen=True)
class ComposerParseResult:
    plainText: str = ""
    contextReferences: list[ContextReference] = field(default_factory=list)
    explicitCommand: CommandInvocation | None = None
    attachments: list[AttachmentReference] = field(default_factory=list)
    parseErrors: list[str] = field(default_factory=list)
