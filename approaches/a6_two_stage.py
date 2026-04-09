"""Two-stage: decompose into sub-goals, then produce JSON."""
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from schema import PLAN_JSON_SCHEMA
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach

STAGE1_SYSTEM = """Decompose a corporate travel request into a flat list of atomic sub-goals.

Each sub-goal is one of:
- "book flight <ORIGIN> -> <DEST> on <DATE> for <NAMES>"
- "book hotel in <CITY> from <CHECK_IN> to <CHECK_OUT> for <NAMES> (<ROOMS> rooms)"

List every atom. Dates in ISO. Output as a JSON array of strings under the key "subgoals":
{"subgoals": ["...", "..."]}
"""


class A6TwoStage(Approach):
    name = "a6_two_stage"

    def predict(self, text):
        c = client()
        r1 = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=[{"role": "system", "content": STAGE1_SYSTEM}, {"role": "user", "content": text}],
            response_format={"type": "json_object"},
        )
        sub = json.loads(r1.choices[0].message.content)
        r2 = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=[
                {"role": "system", "content": SYSTEM_BASE},
                {"role": "user", "content": f"Sub-goals:\n{json.dumps(sub, ensure_ascii=False, indent=2)}\n\nOriginal request:\n{text}\n\nProduce the plan JSON."},
            ],
            response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
        )
        return json.loads(r2.choices[0].message.content)


approach = A6TwoStage()
