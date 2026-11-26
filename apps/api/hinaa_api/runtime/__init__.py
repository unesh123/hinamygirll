"""HINAA Agent OS Runtime Contract package (12-state lifecycle, envelopes, preview & connector audits)."""

from .os_contract import (
    ALLOWED_CAPABILITY_STATES,
    PREVIEW_STAGES,
    CapabilityState,
    PreviewRecord,
    PreviewStage,
    ToolResultEnvelope,
    connector_healthcheck_handler,
    connector_list_handler,
    connector_status_handler,
    connector_test_handler,
    list_previews_snapshot,
    make_tool_envelope,
    register_runtime_os_tools,
)

__all__ = [
    "ALLOWED_CAPABILITY_STATES",
    "PREVIEW_STAGES",
    "CapabilityState",
    "PreviewRecord",
    "PreviewStage",
    "ToolResultEnvelope",
    "connector_healthcheck_handler",
    "connector_list_handler",
    "connector_status_handler",
    "connector_test_handler",
    "list_previews_snapshot",
    "make_tool_envelope",
    "register_runtime_os_tools",
]
