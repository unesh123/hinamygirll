"""The router, tested with the messages the owner measured on the live thread.

Every case below is a message that is NOT a tool request but that the answering
brain -- a flash-tier gateway -- handed one anyway. The gate has to overrule the
model in each of them, and open the one action his own words did ask for.
"""

from __future__ import annotations

import pytest

from hinaa_api.config import Settings
from hinaa_api.models import ToolRequest, TurnRequest
from hinaa_api.prompts import neutral_fallback_plan
from hinaa_api.services import CHARACTER_ENTITY_MAP, ConversationService
from hinaa_api.tools.intent_gate import extract_image_subject, gate_tool_requests, sanction_tools

# What a weak brain writes when it has decided to draw and has nothing to say.
LYING_REPLY = "Sure! I'm generating an image of Naruto for you right now, babe. 🔥"


def _settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL=database_url,
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        ELEVENLABS_API_KEY="",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
    )


@pytest.fixture
def gate_settings():
    return _settings("sqlite+pysqlite:///:memory:")


@pytest.fixture
def temp_db(tmp_path):
    """A file database plus the module-global reset, so the rows this suite
    writes are the only ones its queries can see."""
    from hinaa_api.persistence.db import reset_session_factory

    reset_session_factory()
    yield _settings(f"sqlite+pysqlite:///{(tmp_path / 'gate.db').as_posix()}")
    reset_session_factory()


def _gated(settings, text: str, invented: list[tuple[str, dict]] | None = None, reply: str = LYING_REPLY):
    """Run the turn-path gate over a plan whose tools the model picked itself."""
    service = ConversationService(settings)
    plan = neutral_fallback_plan(user_text=text, companion_id="hinaa", language="en-US", depth="standard")
    plan.displayText = reply
    plan.spokenText = reply
    plan.toolRequests = [ToolRequest(toolName=name, parameters=params) for name, params in (invented or [])]
    service._gate_tool_intents(TurnRequest(sessionId="gate-test", text=text), plan, user_id="gate-user")
    return plan


# --- The five the owner named -------------------------------------------------

def test_isekai_recommendation_gets_no_image_tools(gate_settings):
    """Live proof: a request for recommendations produced `image_search Naruto`."""
    plan = _gated(
        gate_settings,
        "suggest isekai like mushoku and naruto",
        [("image_search", {"query": "Naruto"})],
    )
    assert plan.toolRequests == []


def test_asking_why_an_image_failed_starts_no_image_job(gate_settings):
    """Live proof: his complaint about a failed render became a new render,
    prompted with the complaint itself."""
    complaint = "why did you generate an image i didnt ask for one"
    plan = _gated(gate_settings, complaint, [("image_generate", {"prompt": complaint})])
    assert plan.toolRequests == []
    assert "I did not start an image job because your message was not a request for one." in plan.displayText
    assert complaint not in plan.displayText


def test_a_gated_search_leaves_no_results_caption(gate_settings):
    """Live proof: "image generation is broken" ran nothing and still reported
    "Found 6 relevant Generation Is Broken images.". The router writes that
    caption while it files the call, so it can outlive the call the gate refuses.
    """
    caption = "Found 6 relevant Generation Is Broken images."
    plan = _gated(
        gate_settings,
        "image generation is broken",
        [("image_search", {"query": "Generation Is Broken", "count": 6})],
        reply=caption,
    )
    assert plan.toolRequests == []
    assert "Found 6 relevant" not in plan.displayText
    assert "Found 6 relevant" not in plan.spokenText
    assert "your message was not a request" in plan.displayText


def test_stop_generating_cancels_the_render_and_queues_nothing(temp_db):
    """Live proof: "stop generating" answered with another image job."""
    from sqlalchemy import select

    from hinaa_api.persistence.db import get_session_factory
    from hinaa_api.persistence.orm import GenerationSet, ImageJob

    factory = get_session_factory(temp_db)
    with factory() as session:
        # No conversation_id: that is the shape image_generate files when the
        # thread has no Conversation row, and a conversation-scoped stop found
        # nothing to cancel on exactly these rows.
        group = GenerationSet(user_id="gate-user", prompt="Mikasa", workflow_mode="fast")
        session.add(group)
        session.flush()
        running = ImageJob(generation_set_id=group.id, seed=7, status="processing")
        finished = ImageJob(generation_set_id=group.id, seed=8, status="completed")
        session.add_all([running, finished])
        session.commit()
        running_id, finished_id = running.id, finished.id

    service = ConversationService(temp_db)
    plan = neutral_fallback_plan(
        user_text="stop generating", companion_id="hinaa", language="en-US", depth="standard"
    )
    plan.displayText = LYING_REPLY
    plan.spokenText = LYING_REPLY
    plan.toolRequests = [ToolRequest(toolName="image_generate", parameters={"prompt": "Mikasa"})]
    service._gate_tool_intents(
        TurnRequest(sessionId="gate-test", text="stop generating"), plan, user_id="gate-user"
    )

    assert plan.toolRequests == [], "a stop message queued another render"
    assert plan.displayText == "Stopped. Nothing new was started."
    with factory() as session:
        statuses = dict(session.execute(select(ImageJob.id, ImageJob.status)).all())
    assert statuses[running_id] == "cancelled", "the in-flight render was left running"
    assert statuses[finished_id] == "completed", "a finished job must not be rewritten"


def test_a_stop_says_so_when_the_queue_could_not_be_reached(temp_db, monkeypatch):
    """"Stopped." is only true if something was looked at and cancelled."""
    service = ConversationService(temp_db)
    monkeypatch.setattr(service, "_cancel_inflight_image_jobs", lambda **_kwargs: None)
    plan = neutral_fallback_plan(
        user_text="stop generating", companion_id="hinaa", language="en-US", depth="standard"
    )
    plan.displayText = LYING_REPLY
    plan.spokenText = LYING_REPLY
    service._gate_tool_intents(
        TurnRequest(sessionId="gate-test", text="stop generating"), plan, user_id="gate-user"
    )
    assert "Stopped" not in plan.displayText
    assert plan.displayText == "I could not reach the queue, so the running job may still finish."


def test_reminder_sentence_creates_only_a_reminder(gate_settings):
    """Live proof: he was told to use Siri."""
    plan = _gated(gate_settings, "remind me to call Sile at 4:00")
    assert [tool.toolName for tool in plan.toolRequests] == ["reminder.create"]
    parameters = plan.toolRequests[0].parameters
    assert parameters["title"] == "Call Sile"
    assert parameters["at"].endswith("T16:00"), parameters["at"]
    assert "Siri" not in plan.displayText
    assert "Call Sile" in plan.displayText


def test_generate_mikasa_images_prompts_the_subject_not_the_sentence(gate_settings):
    plan = _gated(gate_settings, "generate mikasa images")
    assert [tool.toolName for tool in plan.toolRequests] == ["image_generate"]
    parameters = plan.toolRequests[0].parameters
    assert parameters["prompt"] == "Mikasa"
    assert parameters["count"] == 1


def test_his_sentence_is_never_filed_as_the_subject_of_the_picture(client):
    """Live proof from the same turn: the prompt was extracted right and the
    subject was not. The job carried `subject_entity: "generate mikasa images"`,
    his own words stamped onto the render as the entity in it, and that field
    steers reference resolution and asset memory downstream."""
    import asyncio

    from hinaa_api.dialogue_state import ConversationTurnState

    owner = client.get(
        "/v1/workspace/identity", headers={"X-HINAA-Dev-User": "gate-subject"}
    ).json()["userId"]
    service = client.app.state.service

    def _plan_with_state(convo: str, text: str, topic: str, entities):
        state = ConversationTurnState.empty(convo, owner)
        state.active_topic = topic
        state.active_entities = entities
        service.dialogue_state_service.save(state)
        result = asyncio.run(
            service.create_plan(
                TurnRequest(
                    sessionId=convo,
                    conversationId=convo,
                    text=text,
                    providerMode="mock",
                ),
                user_id=owner,
            )
        )
        return next(
            tool for tool in result.value.toolRequests if tool.toolName == "image_generate"
        )

    named = _plan_with_state(
        "gate-subject-known",
        "generate mikasa images",
        "generate mikasa images",
        [{"type": "character", "name": "Mikasa Ackerman"}],
    )
    assert named.parameters["prompt"] == "Mikasa"
    assert named.parameters["subject_entity"] == "Mikasa Ackerman"

    # Nothing here names a subject the way a name does: the topic is his sentence
    # and no entity was resolved, so the job ships the extracted prompt and no
    # subject at all. Before the guard it carried `generate zzzqox images` as the
    # entity in the picture.
    unknown = _plan_with_state(
        "gate-subject-unknown",
        "generate zzzqox images",
        "generate pictures of zzzqox",
        [],
    )
    assert unknown.parameters["prompt"] == "Zzzqox"
    assert "subject_entity" not in unknown.parameters


def test_an_explicit_pdf_request_keeps_the_tool_the_router_filed(gate_settings):
    """Two tools build documents and the turn path files `pdf_generate`. A gate
    that sanctioned only the other name answered a real request with prose."""
    plan = _gated(
        gate_settings,
        "make me a pdf about thermohaline circulation",
        [("pdf_generate", {"topic": "thermohaline circulation"})],
    )
    assert [tool.toolName for tool in plan.toolRequests] == ["pdf_generate"]
    assert plan.toolRequests[0].parameters["topic"] == "thermohaline circulation"


def test_one_document_ask_builds_one_file():
    planned = [
        ToolRequest(toolName="pdf_generate", parameters={"topic": "quantum computing"}),
        ToolRequest(toolName="document_generate", parameters={"title": "quantum computing"}),
    ]
    kept, dropped, _ = gate_tool_requests("make me a pdf about quantum computing", planned)
    assert [tool.toolName for tool in kept] == ["pdf_generate"]
    assert dropped == [], "a skipped duplicate is not a refused request"


def test_a_broken_pdf_is_not_a_request_for_a_new_one(gate_settings):
    plan = _gated(gate_settings, "why is the pdf generator broken", [("pdf_generate", {"topic": "pdf"})])
    assert plan.toolRequests == []
    assert "I did not build a document because your message was not a request for one." in plan.displayText


def test_a_verb_naming_a_known_subject_asks_for_a_picture(gate_settings):
    """He has asked for a picture of her by name for months. Requiring the word
    "image" would refuse a turn the router has always honoured."""
    plan = _gated(gate_settings, "Generate Hina sitting in a cafe")
    assert [tool.toolName for tool in plan.toolRequests] == ["image_generate"]
    assert plan.toolRequests[0].parameters["prompt"] == "Hina sitting in a cafe"


def test_a_character_name_does_not_make_a_words_request_a_picture():
    allowed = sanction_tools(
        "generate a list of naruto episodes", known_subjects=CHARACTER_ENTITY_MAP
    ).allowed
    assert not {name for name in allowed if name.startswith("image_")}, allowed


def test_a_variant_of_the_selected_asset_keeps_the_asset():
    """Which picture "the same one" is was resolved from the gallery he clicked
    into, so the call our router built is the one that runs."""
    planned = [
        ToolRequest(toolName="image_generate", parameters={"prompt": "Naruto racing"}),
        ToolRequest(
            toolName="image_generate",
            parameters={
                "prompt": "Same one but darker",
                "reference_images": ["IMG_B"],
                "reference_asset_id": "IMG_B",
            },
        ),
    ]
    kept, dropped, _ = gate_tool_requests("same one but darker", planned)
    assert [tool.parameters.get("reference_asset_id") for tool in kept] == ["IMG_B"]
    assert dropped == [], "a skipped duplicate is not a refused request"


def test_a_variant_ask_with_nothing_selected_starts_nothing(gate_settings):
    plan = _gated(gate_settings, "same one but darker", [("image_generate", {"prompt": "whatever"})])
    assert plan.toolRequests == []
    assert "I don't have the picture you mean, so nothing was started." in plan.displayText
    assert "not a request" not in plan.displayText


# --- The same rule, one message at a time --------------------------------------

@pytest.mark.parametrize(
    "text",
    [
        "image generation is broken",
        "what do you think of naruto",
        "can you draw",
        "draw me",
        "make me a sandwich",
        "stop",
        "cancel that",
        "I didn't ask for that",
        "that wasn't what I asked",
    ],
)
def test_non_requests_never_authorize_image_tools(text):
    allowed = sanction_tools(text).allowed
    assert not {name for name in allowed if name.startswith("image_")}, allowed


@pytest.mark.parametrize(
    "text",
    [
        "generate mikasa images",
        "draw goku going super saiyan",
        "make a picture of nezuko sleeping",
    ],
)
def test_a_real_request_always_carries_an_extracted_subject(text):
    """The prompt is the subject of his sentence. Echoing the sentence is how a
    complaint ended up as the picture.
    """
    parameters = sanction_tools(text).parameters.get("image_generate") or {}
    assert parameters.get("prompt")
    assert parameters["prompt"].lower() in text.lower()
    assert parameters["prompt"] != text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("make me a picture of a red fox", "Red fox"),
        ("please generate 3 images of a cyberpunk city", "Cyberpunk city"),
        ("heya can you create a pic of nezuko for me", "Nezuko"),
        ("generate a wallpaper of your kitchen ultra", "Kitchen"),
        ("render two pictures of a rainy katmandu street", "Rainy katmandu street"),
    ],
)
def test_the_medium_and_the_manner_are_not_the_subject(text, expected):
    assert extract_image_subject(text) == expected


def test_blocked_reply_keeps_his_answer_and_drops_the_false_promise(gate_settings):
    plan = _gated(
        gate_settings,
        "what is mikasa ackerman known for",
        [("image_generate", {"prompt": "Mikasa"})],
    )
    assert plan.toolRequests == []
    assert "generating" not in plan.displayText.lower()
    assert "🔥" not in plan.displayText
    assert plan.displayText.endswith(
        "I did not start an image job because your message was not a request for one."
    )
    assert plan.spokenText == plan.displayText


def test_a_real_answer_survives_when_only_the_promise_is_false():
    answer = "Mikasa Ackerman is the strongest soldier of the Survey Corps."
    promise = "Here's a picture of her 🔥"
    kept = ConversationService._blocked_reply(f"{answer} {promise}", "No image job started.")
    assert kept == f"{answer} No image job started."


def test_the_note_never_fuses_with_a_clause_that_lost_its_end_mark():
    """Measured on the live `stop generating` turn, which read "Stopping now
    Stopped. Nothing new was started." -- two sentences with nothing between."""
    kept = ConversationService._blocked_reply(
        "Got it, babe! Stopping now", "Stopped. Nothing new was started."
    )
    assert kept == "Got it, babe! Stopping now. Stopped. Nothing new was started."


def test_a_promise_about_plural_deliverables_is_still_a_promise():
    """The word boundary after "image" could not match "images", so this class of
    lie survived the strip while STALE_CLAIM already caught it in past tense."""
    kept = ConversationService._blocked_reply(
        "Mikasa is the strongest. I'll generate some images of her right now 🔥",
        "No image job started.",
    )
    assert kept == "Mikasa is the strongest. No image job started."


def test_reminder_tool_is_registered_and_needs_no_confirmation():
    from hinaa_api.tools.registry import registry

    definition = registry.get_tool("reminder.create")
    assert definition is not None, "the reminder tool the owner asked for is not registered"
    assert definition.requires_confirmation is False, (
        "standing consent in /v1/tools/execute does not name this tool, so "
        "requiring confirmation would leave every reminder unanswered"
    )
    assert definition.required_parameters == ["title", "at"]


# --- Persistence: the row is what makes the promise true -----------------------

def test_reminder_persists_and_survives_a_restart(temp_db):
    from datetime import datetime
    from hinaa_api.persistence.db import reset_session_factory
    from hinaa_api.tools.reminder import list_reminders, schedule_reminder

    today_at = datetime.now().strftime("%Y-%m-%dT16:00")
    stored = schedule_reminder(
        user_id="gate-user", title="Call Sile", at=today_at, settings=temp_db
    )
    assert stored["status"] == "scheduled"
    assert stored["display"] == "Today at 4:00 PM"

    reset_session_factory()  # what a backend restart does to the cached engine
    assert [row["title"] for row in list_reminders(user_id="gate-user", settings=temp_db)] == ["Call Sile"]


def test_reminder_is_scoped_to_its_owner(temp_db):
    from hinaa_api.tools.reminder import list_reminders, schedule_reminder

    schedule_reminder(user_id="gate-user", title="Call Sile", at="2026-09-24T16:00", settings=temp_db)
    assert list_reminders(user_id="someone-else", settings=temp_db) == []


def test_a_failed_write_raises_instead_of_reporting_success(temp_db, monkeypatch):
    from hinaa_api.errors import HinaaError
    from hinaa_api.tools import reminder as reminder_module

    def broken(_settings):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(reminder_module, "get_session_factory", broken)
    with pytest.raises(HinaaError) as raised:
        reminder_module.schedule_reminder(user_id="gate-user", title="x", at="2026-09-24T16:00")
    assert "Nothing is scheduled" in str(raised.value)


def test_reminder_endpoints_round_trip(client):
    created = client.post("/v1/reminders", json={"title": "Call Sile", "at": "2026-09-24T16:00"})
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["title"] == "Call Sile" and body["status"] == "scheduled"

    listed = client.get("/v1/reminders").json()
    assert [row["id"] for row in listed] == [body["id"]]

    cancelled = client.post(f"/v1/reminders/{body['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    assert client.get("/v1/reminders").json() == []
    assert client.get("/v1/reminders?status=all").json()[0]["status"] == "cancelled"


def test_reminders_are_not_readable_without_identity(settings):
    """An empty list would read as "no reminders" rather than as "not signed in"."""
    from fastapi.testclient import TestClient

    from hinaa_api.main import create_app

    with TestClient(create_app(settings), base_url="http://127.0.0.1:8000") as anonymous:
        assert anonymous.get("/api/v1/reminders").status_code == 401
        assert anonymous.post(
            "/api/v1/reminders", json={"title": "x", "at": "2026-09-24T16:00"}
        ).status_code == 401


def test_the_arguments_a_call_ran_with_are_not_pasted_into_his_reply(gate_settings):
    """Live bubble from `generate mikasa images`: the job was filed and its own
    argument object arrived again under her sentence, fenced as data."""
    shown = _gated(
        gate_settings,
        "generate mikasa images",
        [("image_generate", {"prompt": "Mikasa", "count": 1})],
        reply='Generating Mikasa Ackerman images for you right now. ```json { '
        '"prompt": "Mikasa Ackerman close up portrait, red scarf", '
        '"aspect_ratio": "1:1", "quality": "hd" } ```',
    ).displayText
    assert "```" not in shown
    assert "aspect_ratio" not in shown
    assert "Generating Mikasa Ackerman images for you right now." in shown


def test_a_turn_with_no_call_keeps_the_json_he_asked_for(gate_settings):
    """The same block on a turn that filed nothing is his answer, not an echo."""
    text = 'The call takes this shape:\n\n```json\n{ "prompt": "a fox", "aspect_ratio": "1:1" }\n```'
    plan = _gated(gate_settings, "what shape does the image call take?", [], reply=text)
    assert plan.displayText == text
