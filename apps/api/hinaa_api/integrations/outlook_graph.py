"""Delegated Microsoft Graph mail access with a Windows user-encrypted token cache."""
from __future__ import annotations
import asyncio
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote
import httpx

from hinaa_api.runtime_paths import runtime_dir

CACHE_PATH = runtime_dir("outlook", "credentials.dpapi")
SCOPES = "offline_access https://graph.microsoft.com/User.Read https://graph.microsoft.com/Mail.ReadWrite"

class OutlookError(RuntimeError):
    pass

def _protect(data: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise OutlookError("The local Outlook cache requires Windows DPAPI. Use a managed secret store on cloud hosts.")
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer)
    target = Blob()
    api = ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not api(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OutlookError("Could not unlock Outlook credentials for this Windows account.")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.windll.kernel32.LocalFree(target.data)

def save_credentials(credentials: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    protected = _protect(json.dumps(credentials).encode())
    temporary = CACHE_PATH.with_suffix(".tmp")
    temporary.write_bytes(protected)
    temporary.replace(CACHE_PATH)

def load_credentials() -> dict:
    try:
        return json.loads(_protect(CACHE_PATH.read_bytes(), decrypt=True))
    except FileNotFoundError:
        return {}
    except (ValueError, OSError) as exc:
        raise OutlookError("Outlook credentials need reconnecting.") from exc

def configured() -> bool:
    # Configuration is not a successful network verification.
    return bool(os.getenv("OUTLOOK_ACCESS_TOKEN") or CACHE_PATH.is_file())

class OutlookGraph:
    def __init__(self):
        self._lock = asyncio.Lock()

    async def token(self) -> str:
        external = os.getenv("OUTLOOK_ACCESS_TOKEN")
        if external:
            return external
        async with self._lock:
            credentials = await asyncio.to_thread(load_credentials)
            if not credentials:
                raise OutlookError("Outlook is disconnected. Run scripts/connect-outlook.py after registering your Microsoft application.")
            if credentials.get("expires_at", 0) > time.time() + 60:
                return credentials["access_token"]
            tenant = credentials.get("tenant", "organizations")
            if not re.fullmatch(r"[A-Za-z0-9.-]+", tenant):
                raise OutlookError("Invalid Microsoft tenant configuration.")
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", data={
                    "grant_type": "refresh_token", "client_id": credentials["client_id"],
                    "refresh_token": credentials["refresh_token"], "scope": credentials["scope"],
                })
            if response.status_code != 200:
                raise OutlookError("Microsoft sign-in expired or was revoked. Reconnect Outlook.")
            tokens = response.json()
            credentials.update(tokens)
            credentials["expires_at"] = time.time() + tokens.get("expires_in", 3600)
            await asyncio.to_thread(save_credentials, credentials)
            return credentials["access_token"]

    async def request(self, method: str, path: str, **kwargs):
        token = await self.token()
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(method, "https://graph.microsoft.com/v1.0" + path,
                headers={"Authorization": "Bearer " + token, "Prefer": 'outlook.body-content-type="text"'}, **kwargs)
        if response.is_error:
            explanations = {401: "Sign-in expired; reconnect Outlook.", 403: "Microsoft denied the mailbox permission. Check consent with your school administrator.", 429: "Microsoft throttled the mailbox. Retry later."}
            raise OutlookError(explanations.get(response.status_code, f"Microsoft Graph request failed ({response.status_code})."))
        return response.json() if response.content else {}

    async def inbox(self, limit: int = 10):
        return await self.request("GET", "/me/mailFolders/inbox/messages", params={
            "$top": min(max(limit, 1), 25), "$orderby": "receivedDateTime desc",
            "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview,webLink",
        })

    async def message(self, message_id: str):
        return await self.request("GET", "/me/messages/" + quote(message_id, safe=""), params={
            "$select": "id,subject,from,toRecipients,receivedDateTime,body,webLink",
        })

    async def draft(self, recipient: str, subject: str, body: str, cc: list[str] | None = None):
        return await self.request("POST", "/me/messages", json=self.payload(recipient, subject, body, cc))

    @staticmethod
    def payload(recipient: str, subject: str, body: str, cc: list[str] | None = None):
        return {"subject": subject, "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": recipient}}],
            "ccRecipients": [{"emailAddress": {"address": address}} for address in cc or []]}

    async def send(self, recipient: str, subject: str, body: str, cc: list[str] | None = None):
        await self.request("POST", "/me/sendMail", json={"message": self.payload(recipient, subject, body, cc), "saveToSentItems": True})
        return {"status": "accepted", "provider": "microsoft-graph", "message": "Microsoft accepted the email for sending. Delivery is not yet verified."}

outlook_graph = OutlookGraph()
