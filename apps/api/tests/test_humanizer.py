from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.humanizer import humanize_text
from hinaa_api.main import create_app


def test_local_humanizer_preserves_protected_technical_content() -> None:
    source = (
        "It is important to note that we should utilize the API in order to start. "
        "See https://example.test/docs and `npm run build`.\n\n"
        "```ts\nconst value = 42;\n```"
    )
    result = humanize_text(source, "natural")

    assert "https://example.test/docs" in result.text
    assert "`npm run build`" in result.text
    assert "const value = 42;" in result.text
    assert "utilize" not in result.text.lower()
    assert result.route == "local-deterministic"
    assert result.externalTextTransfer is False


def test_local_humanizer_preserves_hindi_and_reports_safe_noop() -> None:
    source = "यह draft पहले से साफ़ है। English technical terms stay readable."
    result = humanize_text(source, "warm")

    assert "यह draft" in result.text
    assert result.changes
    assert result.externalTextTransfer is False


def test_humanizer_endpoint_is_private_and_bounded() -> None:
    settings = Settings(HINAA_PROVIDER_MODE="mock", _env_file=None)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/text/humanize",
            json={"text": "Additionally, we utilize this simple example.", "style": "concise"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["route"] == "local-deterministic"
        assert body["externalTextTransfer"] is False
        assert "utilize" not in body["text"].lower()

        invalid = client.post("/v1/text/humanize", json={"text": "x", "style": "mystery"})
        assert invalid.status_code == 422
