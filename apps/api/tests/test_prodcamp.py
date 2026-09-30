import pytest
from unittest.mock import MagicMock, patch
from hinaa_api.tools.prodcamp import (
    prodcamp_list_features,
    prodcamp_submit_feedback,
    prodcamp_create_feature,
    ListFeaturesParams,
    SubmitFeedbackParams,
    CreateFeatureParams,
)

@pytest.mark.asyncio
async def test_prodcamp_list_features_mock():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "items": [
            {
                "id": 101,
                "name": "Autonomous Workflow Pipeline",
                "status": {"caption": "Soon"},
                "priority": {"caption": "High"},
                "upvotesCount": 42,
            }
        ]
    }

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        res = await prodcamp_list_features(ListFeaturesParams(limit=5))
        assert "ProdCamp Product Roadmap" in str(res)
        assert "Autonomous Workflow Pipeline" in str(res)
        assert "Soon" in str(res)

@pytest.mark.asyncio
async def test_prodcamp_submit_feedback_mock():
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": 888}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await prodcamp_submit_feedback(SubmitFeedbackParams(content="We love Hinaa!"))
        assert "Feedback successfully logged to ProdCamp" in str(res)
        assert "#888" in str(res)

@pytest.mark.asyncio
async def test_prodcamp_create_feature_mock():
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": 999}

    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        res = await prodcamp_create_feature(CreateFeatureParams(name="Realtime Voice Streaming"))
        assert "Roadmap Feature Created in ProdCamp" in str(res)
        assert "#999" in str(res)
