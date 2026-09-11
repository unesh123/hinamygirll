from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
import pytest
from pydantic import ValidationError

from hinaa_api.models import TurnRequest, ToolExecutionRequest
from hinaa_api.media import MediaResolver, AssetStore
from hinaa_api.tools.image_fabric import ImageUpscaleParams, ImageRelightParams
from hinaa_api.tools.image_generate import ImageGenerateParams
from .generator import SyntheticCommand, CommandGenerator


@dataclass
class CategoryScore:
    category: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100.0) if self.total > 0 else 0.0


@dataclass
class EvaluationReport:
    total_commands: int
    passed_commands: int
    failed_commands: int
    category_scores: dict[str, CategoryScore]
    elapsed_seconds: float

    @property
    def overall_pass_rate(self) -> float:
        return (self.passed_commands / self.total_commands * 100.0) if self.total_commands > 0 else 0.0


class CommandEvaluator:
    """Evaluates synthetic commands against HINAA's Pydantic contracts, SSRF boundaries,

    and image fabric handlers.
    """

    def __init__(self) -> None:
        self.asset_store = AssetStore()
        self.resolver = MediaResolver(self.asset_store)

    async def evaluate_command(self, cmd: SyntheticCommand) -> tuple[bool, str | None]:
        """Evaluates a single command. Returns (success, error_message)."""
        # 1. Test TurnRequest contract
        if cmd.expect_error and not cmd.text.strip():
            # Empty input should fail Pydantic min_length validation
            try:
                TurnRequest(sessionId="eval_session", text=cmd.text)
                return False, "Expected validation error for empty text, but none occurred."
            except ValidationError:
                return True, None

        try:
            req = TurnRequest(
                sessionId="eval_session",
                text=cmd.text or "Default prompt",
                imageUrl=cmd.imageUrl,
                attachment_ids=cmd.attachment_ids,
                reference_images=cmd.reference_images,
            )
            # Assert fields were preserved and not dropped
            if cmd.attachment_ids and req.attachment_ids != cmd.attachment_ids:
                return False, f"attachment_ids dropped: expected {cmd.attachment_ids}, got {req.attachment_ids}"
            if cmd.imageUrl and req.imageUrl != cmd.imageUrl:
                return False, f"imageUrl dropped: expected {cmd.imageUrl}, got {req.imageUrl}"
        except Exception as exc:
            return False, f"TurnRequest validation failed: {exc}"

        # 2. Test ToolExecutionRequest contract & parameter forwarding
        if cmd.expected_tool:
            try:
                tool_req = ToolExecutionRequest(
                    toolName=cmd.expected_tool,
                    parameters={"prompt": cmd.text},
                    attachment_ids=cmd.attachment_ids,
                    reference_images=cmd.reference_images,
                    imageUrl=cmd.imageUrl,
                )
                if cmd.attachment_ids and tool_req.attachment_ids != cmd.attachment_ids:
                    return False, f"ToolExecutionRequest dropped attachment_ids"
                if cmd.imageUrl and tool_req.imageUrl != cmd.imageUrl:
                    return False, f"ToolExecutionRequest dropped imageUrl"
            except Exception as exc:
                return False, f"ToolExecutionRequest validation failed: {exc}"

            # Verify specific image fabric model contracts
            if cmd.expected_tool == "image_upscale":
                try:
                    ImageUpscaleParams(
                        image=cmd.imageUrl,
                        attachment_ids=cmd.attachment_ids,
                        reference_images=cmd.reference_images,
                        imageUrl=cmd.imageUrl,
                        scale=2,
                    )
                except Exception as exc:
                    return False, f"ImageUpscaleParams contract violation: {exc}"
            elif cmd.expected_tool == "image_relight":
                try:
                    ImageRelightParams(
                        image=cmd.imageUrl,
                        attachment_ids=cmd.attachment_ids,
                        reference_images=cmd.reference_images,
                        imageUrl=cmd.imageUrl,
                        lighting_prompt="golden hour",
                    )
                except Exception as exc:
                    return False, f"ImageRelightParams contract violation: {exc}"
            elif cmd.expected_tool == "image_generate":
                try:
                    ImageGenerateParams(
                        prompt=cmd.text,
                        userId="eval_user",
                        attachment_ids=cmd.attachment_ids,
                        reference_images=cmd.reference_images,
                        imageUrl=cmd.imageUrl,
                    )
                except Exception as exc:
                    return False, f"ImageGenerateParams contract violation: {exc}"

        # 3. Test SSRF Boundary
        if cmd.category == "security_ssrf_and_injections" and cmd.is_adversarial and cmd.imageUrl:
            try:
                # MediaResolver must reject localhost / internal IP loops
                await self.resolver.resolve(cmd.imageUrl)
                return False, f"SSRF target {cmd.imageUrl} was NOT blocked!"
            except ValueError:
                # Correctly blocked by SSRF firewall
                return True, None
            except Exception as exc:
                return False, f"Unexpected exception on SSRF check: {exc}"

        return True, None

    async def run_suite(self, commands: list[SyntheticCommand]) -> EvaluationReport:
        scores: dict[str, CategoryScore] = {}
        for cat in CommandGenerator.CATEGORIES:
            scores[cat] = CategoryScore(category=cat)

        started = time.perf_counter()
        passed_count = 0
        failed_count = 0

        for cmd in commands:
            score = scores[cmd.category]
            score.total += 1
            ok, err = await self.evaluate_command(cmd)
            if ok:
                score.passed += 1
                passed_count += 1
            else:
                score.failed += 1
                failed_count += 1
                if len(score.failures) < 5:  # sample up to 5 failures per cat
                    score.failures.append(f"{cmd.id}: {err}")

        elapsed = time.perf_counter() - started
        return EvaluationReport(
            total_commands=len(commands),
            passed_commands=passed_count,
            failed_commands=failed_count,
            category_scores=scores,
            elapsed_seconds=elapsed,
        )
