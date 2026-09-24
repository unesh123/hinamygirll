import pytest
from hinaa_api.response.intelligence import ResponseIntelligenceController
from hinaa_api.models import AssistantTurnPlan, Emotion, Performance


@pytest.fixture
def controller():
    return ResponseIntelligenceController()


def test_detect_input_echo(controller):
    long_user_prompt = (
        "Here is a detailed specification for the auth token rotation: "
        "Every 15 minutes, fetch a new JWT from the STS service and store it in session storage with AES-256 encryption. "
        "Ensure refresh retry has exponential backoff with jitter."
    )

    # Echoing exact prompt should be detected
    echo_response = f"Here is a detailed specification for the auth token rotation: Every 15 minutes, fetch a new JWT from the STS service and store it in session storage with AES-256 encryption. Ensure refresh retry has exponential backoff with jitter.\n\nNow I will start coding."
    assert controller.detect_input_echo(long_user_prompt, echo_response) is True

    # Normal non-echo response
    good_response = "I have updated the token rotation scheduler to refresh the JWT every 15 minutes with exponential backoff."
    assert controller.detect_input_echo(long_user_prompt, good_response) is False


def test_strip_input_echo(controller):
    user_prompt = "Refactor the database connection pool to 20 connections max."
    assistant_echo = (
        "You asked: Refactor the database connection pool to 20 connections max.\n\n"
        "Here is the updated configuration for the connection pool."
    )
    stripped = controller.strip_input_echo(user_prompt, assistant_echo)
    assert not stripped.startswith("You asked:")
    assert "Here is the updated configuration" in stripped


def test_deduplicate_blocks(controller):
    duplicate_text = (
        "## Setup Instructions\n\n"
        "Run `npm install` in the root directory.\n\n"
        "Run `npm install` in the root directory.\n\n"
        "Next, run `npm test` to verify."
    )
    cleaned = controller.deduplicate_blocks(duplicate_text)
    blocks = cleaned.split("\n\n")
    assert len(blocks) == 3
    assert blocks.count("Run `npm install` in the root directory.") == 1


def test_deduplicate_previous_answer_on_continuation(controller):
    prev_answer = (
        "First, create the migration file in `migrations/versions/001_auth.py`.\n\n"
        "Define the users table with columns id, email, and password_hash."
    )
    # LLM regurgitates prev_answer then adds the continuation
    curr_answer = (
        "First, create the migration file in `migrations/versions/001_auth.py`.\n\n"
        "Define the users table with columns id, email, and password_hash.\n\n"
        "Now, apply the migration by running `alembic upgrade head`."
    )

    result = controller.deduplicate_previous_answer(
        previous_output=prev_answer,
        current_output=curr_answer,
        user_query="continue with the next step",
    )
    assert "Now, apply the migration by running `alembic upgrade head`." in result
    assert "First, create the migration file" not in result


def test_enforce_code_output_rule(controller):
    output = "I implemented the router endpoint."
    written_files = ["apps/api/router.py", "apps/api/auth.py"]
    enforced = controller.enforce_code_output_rule(output, written_files)
    assert "### Modified Workspace Files" in enforced
    assert "`apps/api/router.py`" in enforced
    assert "`apps/api/auth.py`" in enforced


def test_enforce_artifact_output_rule(controller):
    output = "Here is the summary of the quarterly report."
    artifacts = [
        {
            "name": "Q3 Financial Report",
            "kind": "pdf",
            "path": "/artifacts/q3_report.pdf",
            "summary": "Full income statement, balance sheet, and revenue projections.",
        }
    ]
    enforced = controller.enforce_artifact_output_rule(output, artifacts)
    assert "[!NOTE]" in enforced
    assert "**Q3 Financial Report** (PDF)" in enforced
    assert "[Open / Download Artifact](/artifacts/q3_report.pdf)" in enforced


def test_route_response_depth(controller):
    assert controller.route_response_depth("give me a quick tldr") == "QUICK"
    assert controller.route_response_depth("tell me about python") == "NORMAL"
    assert controller.route_response_depth("comprehensive analysis and architectural breakdown") == "DEEP"
    assert controller.route_response_depth("provide a full spec and step-by-step implementation") == "EXHAUSTIVE"
    assert controller.route_response_depth("create a file called report.pdf") == "ARTIFACT"
