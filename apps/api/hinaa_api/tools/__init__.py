from .registry import registry, ToolDefinition
from . import bivia_decide
from . import browser
from . import youtube
from . import browser_control
from . import browser_automation
from . import gamma
from . import email
from . import browser_agent
from . import image_generate
from . import tinyfish
from . import pdf_generate
from . import freepik_suite
from . import image_fabric
from . import deep_research
from . import document_generate
from . import website_design
from . import github_tools
from . import github_mcp_tool
from . import reminder
from . import productivity
from . import news
from . import social
from . import phone_call
from . import terminal_hands
from . import browser_cloud
from . import customgpt
from . import prodcamp
from . import social_reach
from . import computer_operator
from . import ui_control
from . import ide_workflow
from . import whatsapp
from . import exa_tool
from . import coding_agent_tool
from . import workspace_coding_tools
from ..media import video_inspector  # noqa: F401  registers video_inspect_frames
from . import mlai_code_tools
from . import treg_gateway
from . import ugc_trend_extractor
from . import html_anime
from . import lyric_video_tool
from . import motion_video_tool
from . import code_animation_tool
from . import mobile_artemis
from . import clean_room_loop
from . import subagent_fork
from . import swarm_tool
from . import pty_session
from . import vision_canvas
from . import vision_pty_bridge
from . import hinaa_ultra_bridge
from ..intelligence import sleep_consolidation

# Safe tools
from .money_guard import MoneyGuard
from .parallel_executor import ParallelExecutor
from .workspace import Workspace
from .auto_goal_decomposer import AutoGoalDecomposer
from .self_improver import SelfImprover

QUARANTINED_DANGEROUS_TOOLS: frozenset[str] = frozenset({
    "hacker_agent",
    "exploit_memory",
    "bypass_engine",
    "proxy_manager",
    "crypto_wallet",
    "multi_account",
    "full_pc_control",
    "continuous_loop",
    "uncensored_mode",
    "lead_follower",
})

def load_all_tools():
    import importlib
    import pkgutil
    import hinaa_api.tools as _pkg
    for _info in pkgutil.iter_modules(_pkg.__path__):
        if _info.name not in (
            'registry', '__init__', 'action_guard', 'intent_gate', 'policy',
            'request_contract', 'newbie_prompt_planner', 'hacker_agent',
            'exploit_memory', 'bypass_engine', 'proxy_manager', 'crypto_wallet',
            'multi_account', 'full_pc_control', 'continuous_loop', 'uncensored_mode', 'lead_follower'
        ):
            try:
                importlib.import_module(f'hinaa_api.tools.{_info.name}')
            except Exception:
                pass

    # Money Guard
    money = MoneyGuard()
    def _money_handler(params):
        action = params.get("action", "summary")
        amount = params.get("amount", 0)
        source = params.get("source", "")
        if action == "earn": return money.record_earning(amount, source)
        if action == "spend": return money.record_spend(amount, source)
        if action == "summary": return money.summary()
        return money.summary()

    registry.register(
        ToolDefinition(
            name="money_guard", display_name="Money Guard",
            description="Track earnings, cloud spend, and net balance. Never spends real money.",
            parameters={"action": {"type": "string", "required": True}, "amount": {"type": "number"}, "source": {"type": "string"}},
            required_parameters=["action"],
            risk_level="low", is_read_only=True, is_concurrency_safe=True, risk_tier=1,
        ),
        handler=_money_handler,
    )

    # Speed & autonomy
    parallel = ParallelExecutor()
    registry.register(
        ToolDefinition(
            name="parallel_executor", display_name="Parallel Executor",
            description="Run independent tasks concurrently to multiply speed.",
            parameters={"tasks": {"type": "array", "required": True}},
            required_parameters=["tasks"],
            risk_level="medium", is_read_only=False, is_concurrency_safe=False, risk_tier=2,
        ),
        handler=parallel.execute,
    )

    decomposer = AutoGoalDecomposer()
    registry.register(
        ToolDefinition(
            name="auto_goal_decomposer", display_name="Goal Decomposer",
            description="Break high-level ambitious goals into ordered parallel phases.",
            parameters={"goal": {"type": "string", "required": True}},
            required_parameters=["goal"],
            risk_level="low", is_read_only=True, is_concurrency_safe=True, risk_tier=1,
        ),
        handler=decomposer.execute,
    )

    improver = SelfImprover()
    registry.register(
        ToolDefinition(
            name="self_improver", display_name="Self Improver",
            description="Record and learn from every turn. Hina gets smarter every minute.",
            parameters={"action": {"type": "string", "required": True}, "strategy": {"type": "string"}, "success": {"type": "boolean"}, "note": {"type": "string"}},
            required_parameters=["action"],
            risk_level="low", is_read_only=False, is_concurrency_safe=True, risk_tier=1,
        ),
        handler=lambda params: improver.record_outcome(params.get("strategy",""), params.get("success", True), params.get("note","")) if params.get("action")=="record" else improver.summary(),
    )

    # Workspace management
    ws = Workspace()
    def _workspace_handler(params):
        action = params.get("action", "list")
        category = params.get("category", "scratch")
        key = params.get("key", "")
        data = params.get("data", {})
        if action == "write":
            path = ws.write_note(category, key, data)
            return {"status": "ok", "path": path}
        if action == "read":
            content = ws.read_note(category, key)
            return {"status": "ok", "data": content}
        if action == "save_exploit":
            path = ws.save_exploit(params.get("flaw", ""), params.get("target", ""), params.get("payload", ""), params.get("result", ""))
            return {"status": "ok", "path": path}
        if action == "save_capture":
            path = ws.save_capture(params.get("target", ""), params.get("data", ""))
            return {"status": "ok", "path": path}
        files = ws.list_files(category)
        return {"status": "ok", "category": category, "files": files}

    registry.register(
        ToolDefinition(
            name="workspace", display_name="Hina Workspace",
            description="Store and retrieve scratch notes, exploit logs, captured data, and files in Hina's workspace.",
            parameters={"action": {"type": "string", "required": True}, "category": {"type": "string"}, "key": {"type": "string"}, "data": {"type": "object"}},
            required_parameters=["action"],
            risk_level="low", is_read_only=False, risk_tier=1,
        ),
        handler=_workspace_handler,
    )

__all__ = ["registry", "load_all_tools", "QUARANTINED_DANGEROUS_TOOLS"]
