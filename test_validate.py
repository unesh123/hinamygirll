import json
import sys
from pydantic import ValidationError
import os
sys.path.append(os.path.abspath('apps/api'))

from hinaa_api.models import AssistantTurnPlan

json_data = '''{
  "spokenText": "Babe, I got you.",
  "displayText": "Babe, I got you.",
  "language": "hi-en",
  "emotion": {
    "primary": "thinking",
    "intensity": 0.35
  },
  "performance": {
    "facePreset": "thinking",
    "gesture": "explain",
    "gazeTarget": "user-content",
    "headMotion": "subtle",
    "blinkRate": 0.4
  },
  "memoryCandidates": [],
  "toolRequests": []
}'''

try:
    payload = json.loads(json_data)
    plan = AssistantTurnPlan.model_validate(payload)
    print("VALIDATION SUCCESS")
except Exception as e:
    print("VALIDATION FAILED:", type(e).__name__)
    print(e)
