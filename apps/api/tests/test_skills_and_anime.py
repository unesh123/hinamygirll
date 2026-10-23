import pytest
from fastapi.testclient import TestClient

from hinaa_api.main import create_app
from hinaa_api.skills import skill_catalog, skill_router
from hinaa_api.tools import registry
from hinaa_api.tools.html_anime import HtmlAnimeParams, html_anime_handler, render_anime_html
from hinaa_api.tools.intent_gate import anime_will_be_built, sanction_tools


def test_html_anime_tool_registered():
    tool = registry.get_tool("html_anime_generate")
    assert tool is not None
    assert "html_anime_generate" == tool.name
    assert "logline" in tool.parameters


@pytest.mark.asyncio
async def test_html_anime_handler_execution(tmp_path):
    params = HtmlAnimeParams(
        logline="On a rainy neon rooftop, a cyber blade deflects a red laser strike.",
        seconds=8,
        aspect="16:9",
        script="indigo",
        title="Cyber Rooftop Duel",
        dialogue="The rain hid the sound of the blade.",
    )
    result = await html_anime_handler(params)
    assert result["status"] == "success"
    assert result["format"] == "html-anime"
    assert result["seconds"] == 8
    assert result["colorScript"] == "indigo"
    assert "anime_" in result["filename"]


def test_html_anime_render_html():
    raw_html = render_anime_html(
        title="Moonlight Slash",
        logline="A samurai cuts through the moon shadow.",
        seconds=8,
        aspect="16:9",
        script_key="indigo",
        dialogue="Steel speaks in silence.",
    )
    assert "<!doctype html>" in raw_html
    assert 'data-composition-id="moonlight_slash"' in raw_html
    assert 'data-duration="8"' in raw_html
    assert "Steel speaks in silence." in raw_html
    assert "window.__timelines" in raw_html


def test_intent_gate_recognizes_anime_prompts():
    assert anime_will_be_built("Hina, make me an anime animation of a duel on a roof")
    assert anime_will_be_built("create an anime scene about space warriors")
    assert anime_will_be_built("/anime cyber samurai in rain")

    sanction = sanction_tools("Hina, please generate an anime clip of a ninja in the dark")
    assert "html_anime_generate" in sanction.allowed


def test_skill_catalog_indexing():
    skill_catalog.load_all_skills(force_reload=True)
    count = skill_catalog.count()
    assert count >= 100, f"Expected at least 100 skills indexed, got {count}"

    categories = skill_catalog.get_categories()
    assert "Creative & Animation" in categories
    assert "Coding & Engineering" in categories

    anime_skill = skill_catalog.get_skill("html-anime")
    assert anime_skill is not None
    assert "html-anime" in anime_skill.id


def test_skill_router_search():
    skill_router.build_index(force=True)
    matches = skill_router.search("anime animation html", top_k=3)
    assert len(matches) > 0
    top_skill = matches[0].skill
    assert "anime" in top_skill.id.lower() or "anime" in top_skill.name.lower()


def test_skills_api_endpoints():
    app = create_app()
    client = TestClient(app)

    # 1. Categories endpoint
    res_cats = client.get("/api/skills/categories")
    assert res_cats.status_code == 200
    data_cats = res_cats.json()
    assert data_cats["status"] == "ok"
    assert data_cats["totalSkills"] >= 100

    # 2. Search endpoint
    res_search = client.get("/api/skills/search?q=anime")
    assert res_search.status_code == 200
    data_search = res_search.json()
    assert data_search["status"] == "ok"
    assert data_search["count"] >= 1
