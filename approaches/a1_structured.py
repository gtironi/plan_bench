"""gpt-5 + structured output (json_schema)."""
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from schema import PLAN_JSON_SCHEMA
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach


class A1Structured(Approach):
    name = "a1_structured"

    def predict(self, text):
        c = client()
        resp = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=[
                {"role": "system", "content": SYSTEM_BASE},
                {"role": "user", "content": user_prompt(text)},
            ],
            response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
        )
        return json.loads(resp.choices[0].message.content)


approach = A1Structured()
