"""Universal Captcha Solver for HINAA Browser Automation.

Integrates CapSolver (primary, $6 funded) and EZ-Captcha (fallback, $5 funded)
to solve Cloudflare Turnstile, Google reCAPTCHA v2/v3, and image/text captchas
seamlessly during automated browser scraping sessions.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

import httpx

from hinaa_api.config import get_settings

logger = logging.getLogger("hinaa.captcha_solver")


class CaptchaSolver:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def capsolver_key(self) -> str | None:
        if self.settings.capsolver_api_key and self.settings.capsolver_api_key.get_secret_value():
            return self.settings.capsolver_api_key.get_secret_value().strip()
        return os.environ.get("CAPSOLVER_API_KEY")

    @property
    def ez_captcha_key(self) -> str | None:
        if self.settings.ez_captcha_api_key and self.settings.ez_captcha_api_key.get_secret_value():
            return self.settings.ez_captcha_api_key.get_secret_value().strip()
        return os.environ.get("EZ_CAPTCHA_API_KEY")

    async def solve_turnstile(self, website_url: str, website_key: str) -> Optional[str]:
        """Solve Cloudflare Turnstile challenge using CapSolver or EZ-Captcha."""
        # Try CapSolver first
        if self.capsolver_key:
            token = await self._solve_capsolver_turnstile(website_url, website_key)
            if token:
                return token
        # Fallback to EZ-Captcha
        if self.ez_captcha_key:
            return await self._solve_ez_captcha_turnstile(website_url, website_key)
        return None

    async def solve_recaptcha_v2(self, website_url: str, website_key: str) -> Optional[str]:
        """Solve Google reCAPTCHA v2 challenge."""
        if self.capsolver_key:
            token = await self._solve_capsolver_recaptcha_v2(website_url, website_key)
            if token:
                return token
        if self.ez_captcha_key:
            return await self._solve_ez_captcha_recaptcha_v2(website_url, website_key)
        return None

    # --- CapSolver Implementation ---
    async def _solve_capsolver_turnstile(self, website_url: str, website_key: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                create_payload = {
                    "clientKey": self.capsolver_key,
                    "task": {
                        "type": "AntiTurnstileTaskProxyLess",
                        "websiteURL": website_url,
                        "websiteKey": website_key,
                    },
                }
                resp = await client.post("https://api.capsolver.com/createTask", json=create_payload)
                data = resp.json()
                if data.get("errorId", 0) != 0:
                    logger.warning("CapSolver Turnstile createTask failed: %s", data)
                    return None

                task_id = data.get("taskId")
                if not task_id:
                    return None

                # Poll for result
                for _ in range(30):
                    await asyncio.sleep(2)
                    res_resp = await client.post(
                        "https://api.capsolver.com/getTaskResult",
                        json={"clientKey": self.capsolver_key, "taskId": task_id},
                    )
                    res_data = res_resp.json()
                    status = res_data.get("status")
                    if status == "ready":
                        return res_data.get("solution", {}).get("token")
                    if status == "failed":
                        logger.warning("CapSolver Turnstile task failed: %s", res_data)
                        return None
        except Exception as e:
            logger.warning("CapSolver Turnstile error: %s", e)
        return None

    async def _solve_capsolver_recaptcha_v2(self, website_url: str, website_key: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                create_payload = {
                    "clientKey": self.capsolver_key,
                    "task": {
                        "type": "ReCaptchaV2TaskProxyLess",
                        "websiteURL": website_url,
                        "websiteKey": website_key,
                    },
                }
                resp = await client.post("https://api.capsolver.com/createTask", json=create_payload)
                data = resp.json()
                if data.get("errorId", 0) != 0:
                    logger.warning("CapSolver ReCaptchaV2 createTask failed: %s", data)
                    return None

                task_id = data.get("taskId")
                if not task_id:
                    return None

                for _ in range(30):
                    await asyncio.sleep(2)
                    res_resp = await client.post(
                        "https://api.capsolver.com/getTaskResult",
                        json={"clientKey": self.capsolver_key, "taskId": task_id},
                    )
                    res_data = res_resp.json()
                    status = res_data.get("status")
                    if status == "ready":
                        return res_data.get("solution", {}).get("gRecaptchaResponse")
                    if status == "failed":
                        return None
        except Exception as e:
            logger.warning("CapSolver ReCaptchaV2 error: %s", e)
        return None

    # --- EZ-Captcha Implementation ---
    async def _solve_ez_captcha_turnstile(self, website_url: str, website_key: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                create_payload = {
                    "clientKey": self.ez_captcha_key,
                    "task": {
                        "type": "TurnstileTaskProxyless",
                        "websiteURL": website_url,
                        "websiteKey": website_key,
                    },
                }
                resp = await client.post("https://api.ez-captcha.com/createTask", json=create_payload)
                data = resp.json()
                if data.get("errorId", 0) != 0:
                    logger.warning("EZ-Captcha Turnstile createTask failed: %s", data)
                    return None

                task_id = data.get("taskId")
                if not task_id:
                    return None

                for _ in range(30):
                    await asyncio.sleep(2)
                    res_resp = await client.post(
                        "https://api.ez-captcha.com/getTaskResult",
                        json={"clientKey": self.ez_captcha_key, "taskId": task_id},
                    )
                    res_data = res_resp.json()
                    if res_data.get("status") == "ready":
                        return res_data.get("solution", {}).get("token")
                    if res_data.get("status") == "failed":
                        return None
        except Exception as e:
            logger.warning("EZ-Captcha Turnstile error: %s", e)
        return None

    async def _solve_ez_captcha_recaptcha_v2(self, website_url: str, website_key: str) -> Optional[str]:
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                create_payload = {
                    "clientKey": self.ez_captcha_key,
                    "task": {
                        "type": "ReCaptchaV2TaskProxyless",
                        "websiteURL": website_url,
                        "websiteKey": website_key,
                    },
                }
                resp = await client.post("https://api.ez-captcha.com/createTask", json=create_payload)
                data = resp.json()
                if data.get("errorId", 0) != 0:
                    return None

                task_id = data.get("taskId")
                if not task_id:
                    return None

                for _ in range(30):
                    await asyncio.sleep(2)
                    res_resp = await client.post(
                        "https://api.ez-captcha.com/getTaskResult",
                        json={"clientKey": self.ez_captcha_key, "taskId": task_id},
                    )
                    res_data = res_resp.json()
                    if res_data.get("status") == "ready":
                        return res_data.get("solution", {}).get("gRecaptchaResponse")
                    if res_data.get("status") == "failed":
                        return None
        except Exception as e:
            logger.warning("EZ-Captcha ReCaptchaV2 error: %s", e)
        return None


# Global solver instance
captcha_solver = CaptchaSolver()
