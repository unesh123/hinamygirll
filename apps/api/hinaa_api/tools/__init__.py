from .registry import registry
from . import browser
from . import youtube
from . import browser_control

# Playwright-backed browser automation is optional: if the dependency (or a
# browser binary) is not installed, the tools are simply not registered and
# the API reports them as unavailable instead of crashing at import time.
try:  # pragma: no cover - exercised implicitly by import
    from . import browser_automation  # noqa: F401
    from . import browser_agent  # noqa: F401

    BROWSER_AUTOMATION_AVAILABLE = True
except ImportError:  # playwright / google-genai missing
    BROWSER_AUTOMATION_AVAILABLE = False

__all__ = ["registry", "BROWSER_AUTOMATION_AVAILABLE"]
