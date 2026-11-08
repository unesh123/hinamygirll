"""build_with_ide + allow-listed WhatsApp: pure fakes, no browser, no desktop."""

from __future__ import annotations

import asyncio

import pytest

from hinaa_api.errors import HinaaError
from hinaa_api.integrations import whatsapp_guard as guard
from hinaa_api.integrations import whatsapp_web
from hinaa_api.run_ledger import RunLedger
from hinaa_api.tools import ide_workflow as ide
from hinaa_api.tools import policy
from hinaa_api.tools import whatsapp as wa_tool

CANARY_BODY = "super-secret-body-text-123"


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- allow-list


@pytest.mark.parametrize(
    "name", ["Unesh", "AI Hub", "  Unesh  ", "AI\u00a0Hub", "AI   Hub", "\uff35nesh"]
)
def test_allowed_names_normalize(name):
    assert guard.validate_recipient(name) in {"Unesh", "AI Hub"}


@pytest.mark.parametrize(
    "name",
    [
        "unesh",
        "UNESH",
        "ai hub",
        "Unesh B",
        "Unesh\u200b",  # zero-width space
        "Un\u200besh",
        "Un\u200desh",
        "\u0423nesh",  # Cyrillic U
        "Unеsh",  # Cyrillic e
        "AI Hub 2",
        "*",
        "",
        "Unesh,AI Hub",
        "\u202eUnesh",
        None,
        123,
    ],
)
def test_rejected_names(name):
    with pytest.raises(HinaaError) as exc:
        guard.validate_recipient(name)
    assert exc.value.code == "WHATSAPP_RECIPIENT_NOT_ALLOWED"


def test_config_default_and_override():
    assert guard.configured_allowed_chats({}) == ("Unesh", "AI Hub")
    assert guard.configured_allowed_chats({guard.ALLOWED_CHATS_ENV: "Mum, Dev Team"}) == (
        "Mum",
        "Dev Team",
    )
    assert (
        guard.validate_recipient(
            "Mum", guard.configured_allowed_chats({guard.ALLOWED_CHATS_ENV: "Mum"})
        )
        == "Mum"
    )


@pytest.mark.parametrize(
    "value", ["*", "Unesh,*", "Unesh,,AI Hub", ",", "Un*", "Unesh\u200b", "?", "[a]"]
)
def test_config_refuses_empty_or_wildcard(value):
    with pytest.raises(HinaaError) as exc:
        guard.configured_allowed_chats({guard.ALLOWED_CHATS_ENV: value})
    assert exc.value.code == "WHATSAPP_ALLOWLIST_INVALID"


def test_message_validation():
    guard.validate_message("x" * guard.MAX_MESSAGE_CHARS)
    for bad in ("", "   ", "x" * (guard.MAX_MESSAGE_CHARS + 1), None):
        with pytest.raises(HinaaError):
            guard.validate_message(bad)


# ---------------------------------------------------------------- fake page


class FakePage:
    def __init__(
        self,
        *,
        header: str | None = "Unesh",
        logged_in: bool = True,
        header_after_type: str | None = None,
    ):
        self.header = header
        self.header_after_type = header_after_type
        self.logged_in = logged_in
        self.events: list[str] = []
        self.typed: list[str] = []

    async def is_logged_in(self):
        return self.logged_in

    async def open_chat_via_search(self, name):
        self.events.append(f"open:{name}")

    async def read_open_chat_title(self):
        return self.header

    async def type_message(self, text):
        self.events.append("type")
        self.typed.append(text)
        if self.header_after_type is not None:
            self.header = self.header_after_type

    async def press_send(self):
        self.events.append("send")

    async def clear_search(self):
        self.events.append("clear")


def test_driver_sends_when_header_matches():
    page = FakePage(header="AI Hub")
    out = run(whatsapp_web.send_to_allowed_chat(page, "AI Hub", "hello"))
    assert out["recipient"] == "AI Hub" and out["length"] == 5
    assert page.events == ["open:AI Hub", "type", "send"]


@pytest.mark.parametrize("header", ["Unesh Bastola", "unesh", None, "Someone Else", "Unesh\u200b"])
def test_driver_aborts_before_typing_on_header_mismatch(header):
    page = FakePage(header=header)
    with pytest.raises(HinaaError) as exc:
        run(whatsapp_web.send_to_allowed_chat(page, "Unesh", "hello"))
    assert exc.value.code == "WHATSAPP_HEADER_MISMATCH"
    assert "type" not in page.events and "send" not in page.events


def test_driver_aborts_before_send_if_chat_switches_while_typing():
    page = FakePage(header="Unesh", header_after_type="Boss")
    with pytest.raises(HinaaError) as exc:
        run(whatsapp_web.send_to_allowed_chat(page, "Unesh", "hello"))
    assert exc.value.code == "WHATSAPP_HEADER_MISMATCH"
    assert "send" not in page.events


def test_driver_revalidates_recipient_itself():
    page = FakePage()
    with pytest.raises(HinaaError):
        run(whatsapp_web.send_to_allowed_chat(page, "Mom", "hello"))
    assert page.events == []


def test_driver_requires_login():
    page = FakePage(logged_in=False)
    with pytest.raises(HinaaError) as exc:
        run(whatsapp_web.send_to_allowed_chat(page, "Unesh", "hello"))
    assert exc.value.code == "WHATSAPP_NOT_LOGGED_IN"
    assert page.events == []


# ---------------------------------------------------------------- tool + audit


def test_tool_audit_has_no_content(tmp_path, monkeypatch):
    ledger = RunLedger(tmp_path / "ledger.db")
    page = FakePage(header="Unesh")

    async def provider():
        return page

    monkeypatch.setattr(wa_tool, "_page_provider", provider)
    monkeypatch.setattr(wa_tool, "_ledger_provider", lambda: ledger)
    out = run(
        wa_tool.whatsapp_send(wa_tool.WhatsAppSendParams(recipient="Unesh", message=CANARY_BODY))
    )
    assert out["success"] and out["length"] == len(CANARY_BODY)
    rows = ledger.recent_receipts(limit=10)
    assert len(rows) == 1
    assert rows[0]["stepType"] == "whatsapp_send"
    assert rows[0]["metadata"]["recipient"] == "Unesh"
    assert rows[0]["metadata"]["length"] == len(CANARY_BODY)
    assert "timestamp" in rows[0]["metadata"]
    assert CANARY_BODY not in repr(rows)


def test_tool_rejects_bad_recipient_without_touching_browser(monkeypatch):
    async def provider():
        raise AssertionError("browser must not be opened")

    monkeypatch.setattr(wa_tool, "_page_provider", provider)
    with pytest.raises(HinaaError) as exc:
        run(wa_tool.whatsapp_send(wa_tool.WhatsAppSendParams(recipient="unesh", message="hi")))
    assert exc.value.code == "WHATSAPP_RECIPIENT_NOT_ALLOWED"


def test_failed_send_is_audited_without_content(tmp_path, monkeypatch):
    ledger = RunLedger(tmp_path / "ledger.db")

    async def provider():
        return FakePage(header="Impostor")

    monkeypatch.setattr(wa_tool, "_page_provider", provider)
    monkeypatch.setattr(wa_tool, "_ledger_provider", lambda: ledger)
    with pytest.raises(HinaaError):
        run(
            wa_tool.whatsapp_send(
                wa_tool.WhatsAppSendParams(recipient="Unesh", message=CANARY_BODY)
            )
        )
    rows = ledger.recent_receipts(limit=10)
    assert rows[0]["status"] == "failed" and CANARY_BODY not in repr(rows)


# ---------------------------------------------------------------- policy layer


def test_policy_check_arguments():
    policy.check_arguments("whatsapp_send", {"recipient": "Unesh", "message": "hi"})
    policy.check_arguments("web_search", {"recipient": "anyone"})
    for params in (
        {"recipient": "Mom", "message": "hi"},
        {"message": "hi"},
        {"recipient": "Unesh"},
        None,
    ):
        with pytest.raises(HinaaError):
            policy.check_arguments("whatsapp_send", params)


def test_policy_classification():
    assert (
        "whatsapp_send" in policy.LOCAL_EFFECT_TOOLS
        and "whatsapp_send" in policy.IRREVERSIBLE_EXTERNAL_TOOLS
    )
    assert "build_with_ide" in policy.LOCAL_EFFECT_TOOLS


def test_http_rejects_non_allowlisted_even_when_confirmed(client):
    body = {
        "toolName": "whatsapp_send",
        "parameters": {"recipient": "Mom", "message": "hi"},
        "confirmed": True,
        "approvalSource": "user",
    }
    res = client.post("/v1/tools/execute", json=body)
    assert res.status_code == 403
    assert res.json()["code"] == "WHATSAPP_RECIPIENT_NOT_ALLOWED"


@pytest.mark.parametrize(
    "tool,params",
    [
        ("whatsapp_send", {"recipient": "Unesh", "message": "hi"}),
        ("build_with_ide", {"project_name": "site", "brief": "make it"}),
    ],
)
def test_confirmation_required(client, tool, params, monkeypatch):
    monkeypatch.delenv("HINAA_WHATSAPP_AUTOSEND_TO_ALLOWED", raising=False)
    res = client.post("/v1/tools/execute", json={"toolName": tool, "parameters": params})
    assert res.status_code == 409
    assert res.json()["code"] == "TOOL_CONFIRMATION_REQUIRED"
    standing = client.post(
        "/v1/tools/execute",
        json={
            "toolName": tool,
            "parameters": params,
            "confirmed": True,
            "approvalSource": "standing-consent",
        },
    )
    assert standing.status_code == 409


def test_autosend_waives_confirmation_only_for_allowlisted(client, monkeypatch):
    monkeypatch.setenv("HINAA_WHATSAPP_AUTOSEND_TO_ALLOWED", "true")

    async def provider():
        return FakePage(header="Unesh")

    monkeypatch.setattr(wa_tool, "_page_provider", provider)
    monkeypatch.setattr(wa_tool, "_ledger_provider", lambda: None)
    ok = client.post(
        "/v1/tools/execute",
        json={"toolName": "whatsapp_send", "parameters": {"recipient": "Unesh", "message": "hi"}},
    )
    assert ok.status_code == 200, ok.text
    bad = client.post(
        "/v1/tools/execute",
        json={"toolName": "whatsapp_send", "parameters": {"recipient": "Mom", "message": "hi"}},
    )
    assert bad.status_code == 403
    assert not policy.confirmation_waived("build_with_ide")


def test_operator_whatsapp_draft_path_is_allowlisted(monkeypatch):
    monkeypatch.setenv("HINAA_COMPUTER_DRY_RUN", "1")
    from hinaa_api.tools.computer_operator import NativeComputerOperator as Op

    with pytest.raises(HinaaError):
        run(Op.draft_message("whatsapp", "hi", "+9779800000000"))
    with pytest.raises(HinaaError):
        run(Op.draft_message("whatsapp", "hi", None))


# ---------------------------------------------------------------- build_with_ide


class FakeProc:
    def __init__(self, rc=None):
        self.rc = rc

    def poll(self):
        return self.rc


class Desktop:
    """Minimal fake desktop recording every effect."""

    def __init__(self, *, windows_visible=True, focus_works=True, proc_rc=None):
        self.calls: list = []
        self.windows_visible = windows_visible
        self.focus_works = focus_works
        self.proc_rc = proc_rc
        self.title = "Desktop"
        self.clip: str | None = None
        self.folder_name = ""

    def ports(self, dry=False, tmp=None):
        async def sleep(_):
            return None

        async def list_windows():
            return [{"title": f"{self.folder_name} - Antigravity"}] if self.windows_visible else []

        async def focus(target):
            self.calls.append(("focus", target))
            if self.focus_works:
                self.title = f"{target} - Antigravity"
            return self.focus_works

        async def hotkey(keys):
            self.calls.append(("hotkey", keys))
            return True

        async def set_clip(text):
            self.clip = text
            return True

        def launch(argv):
            self.calls.append(("launch", list(argv)))
            self.folder_name = argv[-1].replace("\\", "/").rsplit("/", 1)[-1]
            return FakeProc(self.proc_rc)

        return ide.IdePorts(
            launch=launch,
            list_windows=list_windows,
            active_title=lambda: self.title,
            focus=focus,
            hotkey=hotkey,
            set_clipboard=set_clip,
            get_clipboard=lambda: self.clip,
            sleep=sleep,
            dry_run=lambda: dry,
            which=lambda name: f"/bin/{name}" if name == "cursor" else None,
            windows=False,
            exists=lambda p: False,
        )


def env_for(tmp_path, **extra):
    return {"HINAA_PROJECTS_ROOT": str(tmp_path / "projects"), **extra}


def test_slug_rejects_traversal_and_sanitizes():
    for bad in ["../evil", "a/b", "a\\b", "..", "", "   ", "C:\\x", "x/../y", "\u2025"]:
        with pytest.raises(HinaaError):
            ide.slugify_project_name(bad)
    assert ide.slugify_project_name("My Cool Site!!") == "my-cool-site"


def test_dry_run_plans_without_effects(tmp_path):
    d = Desktop()
    out = run(
        ide.build_with_ide(
            ide.BuildWithIdeParams(project_name="Shop", brief="build a shop"),
            ports=d.ports(dry=True),
            env=env_for(tmp_path),
        )
    )
    assert out["dry_run"] and out["success"] and out["ide"] == "cursor"
    assert any("PROMPT.md" in s for s in out["planned_steps"])
    assert not (tmp_path / "projects").exists()
    assert d.calls == [] and d.clip is None


def test_full_workflow_creates_folder_prompt_and_pastes(tmp_path):
    d = Desktop()
    brief = "Build a shop.\nUse React. ünïcode"
    ledger = RunLedger(tmp_path / "l.db")
    out = run(
        ide.build_with_ide(
            ide.BuildWithIdeParams(project_name="Shop", brief=brief),
            ports=d.ports(),
            env=env_for(tmp_path, HINAA_IDE_AGENT_SHORTCUT="ctrl+shift+i"),
            ledger=ledger,
        )
    )
    assert out["success"], out
    folder = tmp_path / "projects" / "shop"
    assert folder.is_dir() and (folder / "PROMPT.md").read_text(encoding="utf-8") == brief
    launches = [c for c in d.calls if c[0] == "launch"]
    assert launches == [("launch", ["/bin/cursor", str(folder)])]
    assert [c[1] for c in d.calls if c[0] == "hotkey"] == ["ctrl+shift+i", "ctrl+v", "enter"]
    assert d.clip == brief
    assert all(r["verified"] for r in out["receipts"]) and len(out["receipts"]) == 9
    assert len(ledger.recent_receipts(limit=50)) == 9


def test_existing_folder_is_not_overwritten(tmp_path):
    (tmp_path / "projects" / "shop").mkdir(parents=True)
    (tmp_path / "projects" / "shop" / "PROMPT.md").write_text("old")
    d = Desktop()
    out = run(
        ide.build_with_ide(
            ide.BuildWithIdeParams(project_name="shop", brief="new"),
            ports=d.ports(),
            env=env_for(tmp_path),
        )
    )
    assert out["success"] and out["folder"].endswith("shop-2")
    assert (tmp_path / "projects" / "shop" / "PROMPT.md").read_text() == "old"


def test_no_keystrokes_when_window_never_appears(tmp_path):
    d = Desktop(windows_visible=False)
    out = run(
        ide.build_with_ide(
            ide.BuildWithIdeParams(project_name="x1", brief="b"),
            ports=d.ports(),
            env=env_for(tmp_path),
        )
    )
    assert not out["success"] and out["stopped_reason"] == "ide_window_not_observed"
    assert not [c for c in d.calls if c[0] in ("hotkey", "focus")]


def test_no_keystrokes_when_focus_fails(tmp_path):
    d = Desktop(focus_works=False)
    out = run(
        ide.build_with_ide(
            ide.BuildWithIdeParams(project_name="x2", brief="b"),
            ports=d.ports(),
            env=env_for(tmp_path),
        )
    )
    assert out["stopped_reason"] == "ide_not_focused"
    assert not [c for c in d.calls if c[0] == "hotkey"]


def test_launch_failure_exit_code_stops(tmp_path):
    d = Desktop(proc_rc=1)
    out = run(
        ide.build_with_ide(
            ide.BuildWithIdeParams(project_name="x3", brief="b"),
            ports=d.ports(),
            env=env_for(tmp_path),
        )
    )
    assert out["stopped_reason"] == "launch_failed"


def test_submit_false_skips_enter(tmp_path):
    d = Desktop()
    out = run(
        ide.build_with_ide(
            ide.BuildWithIdeParams(project_name="x4", brief="b", submit=False),
            ports=d.ports(),
            env=env_for(tmp_path),
        )
    )
    assert out["success"] and [c[1] for c in d.calls if c[0] == "hotkey"] == ["ctrl+l", "ctrl+v"]


def test_command_resolution_fallbacks():
    only = lambda found: lambda name: f"/x/{name}" if name == found else None  # noqa: E731
    assert ide.resolve_ide_command({}, which=only("antigravity"), windows=False)[1] == "antigravity"
    assert ide.resolve_ide_command({}, which=only("cursor"), windows=False)[1] == "cursor"
    assert ide.resolve_ide_command({}, which=only("code"), windows=False)[1] == "code"
    with pytest.raises(HinaaError) as exc:
        ide.resolve_ide_command({}, which=lambda n: None, windows=False)
    assert exc.value.code == "IDE_NOT_FOUND"
    # configured command is used alone, args preserved as argv items
    argv, name = ide.resolve_ide_command(
        {"HINAA_IDE_COMMAND": "windsurf --new-window"}, which=only("windsurf"), windows=False
    )
    assert argv == ["/x/windsurf", "--new-window"]
    with pytest.raises(HinaaError):
        ide.resolve_ide_command(
            {"HINAA_IDE_COMMAND": "windsurf"}, which=only("code"), windows=False
        )


def test_windows_install_path_fallback():
    local = r"C:\Users\u\AppData\Local"
    target = local + r"\Programs\Antigravity\Antigravity.exe"
    argv, name = ide.resolve_ide_command(
        {"LOCALAPPDATA": local}, which=lambda n: None, windows=True, exists=lambda p: p == target
    )
    assert argv == [target] and name == "antigravity"


def test_chord_conversion():
    from hinaa_api.tools.computer_operator import _sendkeys_chord

    assert _sendkeys_chord("ctrl+l") == "^l"
    assert _sendkeys_chord("ctrl+shift+i") == "^+i"
    assert _sendkeys_chord("f5") == "f5"
