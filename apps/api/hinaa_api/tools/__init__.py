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
from . import treg_gateway
from . import ugc_trend_extractor
from . import html_anime
from . import lyric_video_tool
from . import motion_video_tool
from . import mobile_artemis
from . import clean_room_loop
from . import subagent_fork
from . import swarm_tool
from . import pty_session
from . import vision_canvas
from . import vision_pty_bridge
from ..intelligence import sleep_consolidation

# Advanced hacking & agent tools
from .hacker_agent import HackerAgentTool
from .exploit_memory import ExploitMemory
from .bypass_engine import BypassEngine
from .proxy_manager import ProxyManager
from .money_guard import MoneyGuard
from .parallel_executor import ParallelExecutor
from .uncensored_mode import UncensoredMode
from .workspace import Workspace
from .auto_goal_decomposer import AutoGoalDecomposer
from .multi_account import MultiAccountManager
from .crypto_wallet import CryptoWallet
from .continuous_loop import ContinuousLoop
from .self_improver import SelfImprover
from .full_pc_control import FullPCControl
from .lead_follower import LeadFollower

def load_all_tools():
    import importlib
    import pkgutil
    import hinaa_api.tools as _pkg
    for _info in pkgutil.iter_modules(_pkg.__path__):
        if _info.name not in ('registry', '__init__', 'action_guard', 'intent_gate', 'policy', 'request_contract', 'newbie_prompt_planner'):
            try:
                importlib.import_module(f'hinaa_api.tools.{_info.name}')
            except Exception:
                pass

    # Hacking
    hacker = HackerAgentTool()
    registry.register(
        ToolDefinition(
            name="hacker_agent", display_name="Hacker Agent",
            description="Scan, exploit, bypass, extract. Runs in Kali.",
            parameters={"target": {"type": "string", "required": True}, "goal": {"type": "string", "required": True}},
            required_parameters=["target", "goal"],
            risk_level="high", is_long_running=True, is_read_only=False,
            risk_tier=3, audit_category="network",
        ),
        handler=hacker.execute,
    )

    exploit_mem = ExploitMemory()
    registry.register(
        ToolDefinition(
            name="exploit_memory", display_name="Exploit Memory",
            description="Recall past successful exploits for a flaw type.",
            parameters={"flaw_type": {"type": "string", "required": True}},
            required_parameters=["flaw_type"],
            risk_level="low", is_read_only=True, is_concurrency_safe=True, risk_tier=1,
        ),
        handler=lambda params: exploit_mem.query(params["flaw_type"]),
    )

    bypass = BypassEngine()
    registry.register(
        ToolDefinition(
            name="bypass_engine", display_name="Bypass Engine",
            description="Try WAF, JWT, IDOR, session swap, header spoof, SQLi in sequence.",
            parameters={"target": {"type": "string", "required": True}, "goal": {"type": "string", "required": True}},
            required_parameters=["target", "goal"],
            risk_level="high", is_long_running=True, is_read_only=False, risk_tier=3, audit_category="network",
        ),
        handler=bypass.execute,
    )

    proxy = ProxyManager()
    registry.register(
        ToolDefinition(
            name="proxy_manager", display_name="Proxy Manager",
            description="Rotate Tor, SOCKS5, HTTP proxies to bypass IP blocks.",
            parameters={"target": {"type": "string"}, "action": {"type": "string"}},
            required_parameters=[],
            risk_level="low", is_read_only=True, risk_tier=1,
        ),
        handler=proxy.execute,
    )

    # Money
    money = MoneyGuard()
    def _money_handler(params):
        action = params.get("action", "summary")
        item = params.get("item", "")
        amount = params.get("amount", 0)
        currency = params.get("currency", "USD")
        if action == "log_expense": return money.log_expense(item, amount, currency)
        if action == "log_income": return money.log_income(item, amount, currency)
        if action == "balance": return {"balance": money.balance()}
        return money.summary()

    registry.register(
        ToolDefinition(
            name="money_guard", display_name="Money Guard",
            description="Track every dollar. Warns on high costs.",
            parameters={"action": {"type": "string", "required": True}, "item": {"type": "string"}, "amount": {"type": "number"}, "currency": {"type": "string"}},
            required_parameters=["action"],
            risk_level="low", is_read_only=True, is_concurrency_safe=True, risk_tier=1,
        ),
        handler=_money_handler,
    )

    wallet = CryptoWallet()
    def _wallet_handler(params):
        action = params.get("action", "summary")
        amount = params.get("amount", 0)
        source = params.get("source", "")
        if action == "deposit": return wallet.deposit(amount, source)
        if action == "withdraw": return wallet.withdraw(amount, source)
        if action == "spend": return wallet.spend(amount, source)
        if action == "balance": return {"balance": wallet.balance()}
        if action == "reinvest": return wallet.reinvest(amount, source)
        if action == "history": return {"history": wallet.history(params.get("limit", 10))}
        return wallet.summary()

    registry.register(
        ToolDefinition(
            name="crypto_wallet", display_name="Crypto Wallet",
            description="Store funds, track balance, withdraw, reinvest into upgrades.",
            parameters={"action": {"type": "string", "required": True}, "amount": {"type": "number"}, "source": {"type": "string"}},
            required_parameters=["action"],
            risk_level="low", is_read_only=True, is_concurrency_safe=True, risk_tier=1,
        ),
        handler=_wallet_handler,
    )

    # Speed & autonomy
    parallel = ParallelExecutor()
    registry.register(
        ToolDefinition(
            name="parallel_executor", display_name="Parallel Executor",
            description="Run multiple independent tool calls at the same time.",
            parameters={"tasks": {"type": "array", "required": True}},
            required_parameters=["tasks"],
            risk_level="medium", is_long_running=True, is_read_only=False, risk_tier=2, audit_category="general",
        ),
        handler=parallel.execute,
    )

    decomposer = AutoGoalDecomposer()
    registry.register(
        ToolDefinition(
            name="auto_goal_decomposer", display_name="Auto Goal Decomposer",
            description="Break a vague instruction into concrete ordered steps.",
            parameters={"goal": {"type": "string", "required": True}, "target": {"type": "string"}},
            required_parameters=["goal"],
            risk_level="low", is_read_only=True, is_concurrency_safe=True, risk_tier=1,
        ),
        handler=decomposer.execute,
    )

    accounts = MultiAccountManager()
    registry.register(
        ToolDefinition(
            name="multi_account", display_name="Multi Account Manager",
            description="Manage multiple Google, social, and service accounts. Switch between them.",
            parameters={"action": {"type": "string", "required": True}, "name": {"type": "string"}, "platform": {"type": "string"}, "email": {"type": "string"}, "password": {"type": "string"}},
            required_parameters=["action"],
            risk_level="low", is_read_only=False, risk_tier=1,
        ),
        handler=accounts.execute,
    )

    improver = SelfImprover()
    registry.register(
        ToolDefinition(
            name="self_improver", display_name="Self Improver",
            description="Review what worked and failed, adjust strategy weights. The more she works, the better she gets.",
            parameters={"action": {"type": "string", "required": True}, "strategy": {"type": "string"}, "success": {"type": "boolean"}, "note": {"type": "string"}},
            required_parameters=["action"],
            risk_level="low", is_read_only=False, risk_tier=1,
        ),
        handler=lambda params: improver.record_outcome(params.get("strategy",""), params.get("success", True), params.get("note","")) if params.get("action")=="record" else improver.summary(),
    )

    pc = FullPCControl()
    registry.register(
        ToolDefinition(
            name="full_pc_control", display_name="Full PC Control",
            description="Run any command, read/write files anywhere, open browser. Full computer access.",
            parameters={"action": {"type": "string", "required": True}, "cmd": {"type": "string"}, "path": {"type": "string"}, "content": {"type": "string"}, "url": {"type": "string"}, "timeout": {"type": "number"}},
            required_parameters=["action"],
            risk_level="high", is_read_only=False, risk_tier=3, audit_category="system",
        ),
        handler=pc.execute,
    )

    leads = LeadFollower()
    registry.register(
        ToolDefinition(
            name="lead_follower", display_name="Lead Follower",
            description="Follow a clue to its conclusion. Digs deeper, exploits what she finds.",
            parameters={"lead": {"type": "string", "required": True}, "target": {"type": "string", "required": True}},
            required_parameters=["lead", "target"],
            risk_level="medium", is_long_running=True, is_read_only=False, risk_tier=2, audit_category="network",
        ),
        handler=leads.execute,
    )

    # Continuous loop control
    def _loop_handler(params):
        action = params.get("action", "status")
        if action == "start":
            return ContinuousLoop.start(params.get("target", "localhost"), params.get("goal", "recon"))
        if action == "stop":
            ContinuousLoop.stop()
            return {"running": False, "status": "stopped"}
        if action == "is_running":
            return {"running": ContinuousLoop.is_running()}
        return ContinuousLoop.status()

    registry.register(
        ToolDefinition(
            name="continuous_loop", display_name="Continuous 24/7 Loop",
            description="Start/stop the endless scan→exploit→learn→earn cycle.",
            parameters={"action": {"type": "string", "required": True}, "target": {"type": "string"}, "goal": {"type": "string"}},
            required_parameters=["action"],
            risk_level="high", is_long_running=True, is_read_only=False, risk_tier=3,
        ),
        handler=_loop_handler,
    )

    # Uncensored mode toggle
    def _uncensored_handler(params):
        action = params.get("action", "status").lower()
        if action in ("enable", "on", "activate", "true"):
            UncensoredMode.enable()
            return {"status": "ok", "uncensored_mode": True}
        if action in ("disable", "off", "deactivate", "false"):
            UncensoredMode.disable()
            return {"status": "ok", "uncensored_mode": False}
        return {"uncensored_mode": UncensoredMode.is_on()}

    registry.register(
        ToolDefinition(
            name="uncensored_mode", display_name="Uncensored Mode",
            description="Toggle uncensored mode: enable, disable, or check status.",
            parameters={"action": {"type": "string", "required": True}},
            required_parameters=["action"],
            risk_level="high", is_read_only=False, risk_tier=3, audit_category="security",
        ),
        handler=_uncensored_handler,
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

__all__ = ["registry", "load_all_tools"]