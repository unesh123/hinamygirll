from .registry import registry
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
from . import terminal_hands
from . import browser_cloud
from . import customgpt
from . import prodcamp
from . import social_reach
from . import computer_operator
from . import ui_control
from . import exa_tool
from . import coding_agent_tool
from . import treg_gateway
from . import ugc_trend_extractor
from . import html_anime
from . import mobile_artemis
from . import clean_room_loop
from . import subagent_fork
from . import swarm_tool
from . import pty_session
from . import vision_canvas
from . import vision_pty_bridge
from ..intelligence import sleep_consolidation

def load_all_tools():
    """Import all tool modules to ensure they register with the registry."""
    import importlib
    import pkgutil
    import hinaa_api.tools as _pkg
    for _info in pkgutil.iter_modules(_pkg.__path__):
        if _info.name not in ('registry', '__init__', 'action_guard', 'intent_gate', 'policy', 'request_contract', 'newbie_prompt_planner'):
            try:
                importlib.import_module(f'hinaa_api.tools.{_info.name}')
            except Exception:
                pass


__all__ = ["registry", "load_all_tools"]

