"""Reasoning model (o-series) with high reasoning effort."""
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_REASONING
from schema import PLAN_JSON_SCHEMA
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach


class A2Reasoning(Approach):
    name = "a2_reasoning"

    def predict(self, text):
        c = client()
        resp = c.chat.completions.create(
            model=MODEL_REASONING,
            messages=[
                {"role": "system", "content": SYSTEM_BASE + "\n\nThink carefully about every traveler, city, and date before producing the JSON."},
                {"role": "user", "content": user_prompt(text)},
            ],
            reasoning_effort="high",
            response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
        )
        return json.loads(resp.choices[0].message.content)


approach = A2Reasoning()
