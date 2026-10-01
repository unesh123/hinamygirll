"""
Test Suite for Desktop AgentOS (HostAgent + AppAgents UFO² Paradigm).
"""

import pytest
from hinaa_api.desktop.agent_os import (
    HostAgent,
    BrowserAppAgent,
    WhatsAppAppAgent,
    VSCodeAppAgent,
    TerminalAppAgent,
    GeneralUIAgent,
    ActionPriorityLevel,
    SubTaskPlan,
)


@pytest.mark.asyncio
async def test_host_agent_task_dag_planning():
    host = HostAgent()
    plan = host.plan_task_dag("Research deployment logs in browser and send summary to whatsapp")
    assert len(plan) == 2
    assert plan[0].target_app == "browser"
    assert plan[0].priority_level == ActionPriorityLevel.BROWSER_DOM
    assert plan[1].target_app == "whatsapp"
    assert plan[1].priority_level == ActionPriorityLevel.UI_AUTOMATION
    assert plan[1].requires_confirmation is True


@pytest.mark.asyncio
async def test_app_agent_routing():
    host = HostAgent()
    assert isinstance(host.route_to_app_agent("browser"), BrowserAppAgent)
    assert isinstance(host.route_to_app_agent("whatsapp"), WhatsAppAppAgent)
    assert isinstance(host.route_to_app_agent("vscode"), VSCodeAppAgent)
    assert isinstance(host.route_to_app_agent("terminal"), TerminalAppAgent)
    assert isinstance(host.route_to_app_agent("custom_window"), GeneralUIAgent)


@pytest.mark.asyncio
async def test_whatsapp_app_agent_safety_staging():
    agent = WhatsAppAppAgent()
    task = SubTaskPlan(
        task_id="t1",
        target_app="whatsapp",
        description="Draft status",
        action="draft_message",
        params={"text": "All services nominal", "recipient": "Lead"},
        priority_level=ActionPriorityLevel.UI_AUTOMATION,
    )
    res = await agent.execute_task(task)
    assert res.success is True
    assert res.verified is True
    assert res.output_data is not None
    assert "confirmation_token" in res.output_data


@pytest.mark.asyncio
async def test_browser_app_agent_execution():
    agent = BrowserAppAgent()
    task = SubTaskPlan(
        task_id="t2",
        target_app="browser",
        description="Search documentation",
        action="search",
        params={"query": "OpenTelemetry tracing python"},
        priority_level=ActionPriorityLevel.BROWSER_DOM,
    )
    res = await agent.execute_task(task)
    assert res.success is True
    assert res.priority_used == ActionPriorityLevel.BROWSER_DOM


@pytest.mark.asyncio
async def test_speculative_mission_execution():
    host = HostAgent()
    results = await host.execute_mission("play daft punk on spotify", speculative=True)
    assert len(results) > 0
    assert results[0].success is True
