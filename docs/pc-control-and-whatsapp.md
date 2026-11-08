# PC control workflows and the WhatsApp messenger

Two local-effect tools for the owner's Windows PC. Both run on the machine hosting the API, are loopback-only
(`tools/policy.py`), and require explicit user confirmation.

## `build_with_ide`

"Go to Antigravity and build this website."

1. Creates `<HINAA_PROJECTS_ROOT>/<slug>` (default `~/HinaProjects/<slug>`). The slug is `[a-z0-9-]` only; names
   containing `/`, `\`, `:` or `..` are rejected. An existing folder is never reused (`-2`, `-3`, ... suffix).
2. Writes the full brief to `PROMPT.md` (UTF-8).
3. Launches the IDE with an argv list (never a shell). `HINAA_IDE_COMMAND` is used alone when set; otherwise
   `antigravity`, `cursor`, `code` are tried on `PATH` and, on Windows, under
   `%LOCALAPPDATA%\Programs\{Antigravity,cursor,Microsoft VS Code}`.
4. Waits for a window whose title contains the folder name, focuses it, copies the brief to the clipboard,
   presses `HINAA_IDE_AGENT_SHORTCUT` (default `ctrl+l`), `ctrl+v`, and `enter` (`submit=false` skips Enter).
5. Every step is an ActionGuard step with a receipt and a run-ledger row. If a step fails verification the workflow
   stops (it never types into a window it could not confirm is the IDE) and returns `stopped_reason`.

`HINAA_COMPUTER_DRY_RUN=1` returns `planned_steps` and touches nothing. Generic app launching is the existing
`app_launch` tool. Limit: the pasted text is not observable from outside the IDE, so the paste/submit receipts prove
the keystrokes reached the IDE window, not the chat contents. The agent-chat shortcut differs per IDE; set it if
`ctrl+l` is wrong for yours.

## `whatsapp_send` / `whatsapp_status`

**Hard rule:** only the chats named exactly `Unesh` and `AI Hub` can receive messages. Matching is exact and
case-sensitive after Unicode NFKC and whitespace normalisation; lookalikes, `unesh`, trailing text and zero-width
characters are refused. Text only, max 2000 characters, no media, no new chats.

Three independent enforcement layers:

1. **Tool arguments** (`tools/whatsapp.py`, `integrations/whatsapp_guard.py`): the recipient is validated before any
   browser work.
2. **Policy** (`tools/policy.py: check_arguments`): runs on both dispatch paths in `main.py` (HTTP tool execute and the
   agent runtime), before confirmation is considered. `whatsapp_send` is also in `IRREVERSIBLE_EXTERNAL_TOOLS`, so it
   needs a loopback Host.
3. **Browser driver** (`integrations/whatsapp_web.py`): re-validates, opens the chat by exact-title search result, reads
   the open chat's header from the DOM and aborts unless it equals the name, types, then re-reads the header
   immediately before pressing send.

The legacy `computer_operator` WhatsApp draft path applies the same allow-list.

Configuration: `HINAA_WHATSAPP_ALLOWED_CHATS` (comma separated; empty entries and wildcards are refused, so a bad
value fails closed). `HINAA_WHATSAPP_AUTOSEND_TO_ALLOWED=true` skips the confirmation prompt, only for allow-listed
sends. Confirmation is otherwise required.

Audit: each send writes a run-ledger receipt (`step_type=whatsapp_send`) with recipient, length and timestamp. The
message body is never logged.

Setup: the browser profile is `.runtime/whatsapp-profile` (gitignored; override with `HINAA_WHATSAPP_PROFILE_DIR`).
Run `whatsapp_status` once, scan the QR code in the window that opens, and the session persists. The window is visible
by default (`HINAA_WHATSAPP_HEADLESS=true` to hide it; WhatsApp Web is less reliable headless).

Maintenance: all selectors are in `integrations/whatsapp_selectors.py`. WhatsApp Web changes its DOM without notice;
a `WHATSAPP_SELECTOR_MISSING` error means update that file. This code is tested against a fake page only, not the live
site. Generic keyboard control (`computer_operator type_text`) is not content-aware and can still type into any focused
window; the allow-list covers the WhatsApp tools and the WhatsApp draft path.

Settings are read from the process environment, like `HINAA_COMPUTER_DRY_RUN`.
