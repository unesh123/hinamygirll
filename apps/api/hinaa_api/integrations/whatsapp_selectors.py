"""All WhatsApp Web DOM selectors live here.

WhatsApp Web changes its markup without notice. When sending starts failing
with WHATSAPP_SELECTOR_MISSING, update this file only. Prefer aria-label,
data-testid and role over generated class names; each entry is tried in order.
"""

from __future__ import annotations

WEB_URL = "https://web.whatsapp.com/"

# Present only when a session is linked.
CHAT_LIST = ('[aria-label="Chat list"]', '[data-testid="chat-list"]', "#pane-side")
# Present only on the QR-pairing screen.
QR_CODE = ('[data-testid="qrcode"]', 'canvas[aria-label*="QR" i]', '[aria-label*="Scan this QR" i]')

SEARCH_BOX = (
    '[data-testid="chat-list-search"]',
    'div[contenteditable="true"][role="textbox"][aria-label*="Search" i]',
    'div[contenteditable="true"][data-tab="3"]',
)
# Exact-title result rows; {name} is substituted with an attribute-escaped name.
SEARCH_RESULT_TITLE = ('#pane-side span[title="{name}"]',)

# Title of the currently open conversation.
OPEN_CHAT_TITLE = (
    '[data-testid="conversation-info-header-chat-title"]',
    "#main header span[title]",
)
COMPOSER = (
    '[data-testid="conversation-compose-box-input"]',
    '#main footer div[contenteditable="true"][role="textbox"]',
    '#main footer div[contenteditable="true"]',
)
SEND_BUTTON = ('[data-testid="send"]', '#main footer button[aria-label="Send"]')


def css_attr_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
