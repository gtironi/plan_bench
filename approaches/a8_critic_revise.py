"""Generator → Critic → Reviser."""
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from schema import PLAN_JSON_SCHEMA
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach

CRITIC_SYSTEM = """You are a strict reviewer of corporate travel plans.
Given the original request and a candidate JSON plan, list every concrete divergence:
missing travelers, missing flight legs, wrong dates, wrong cities/IATA, wrong traveler assignments,
wrong cabin, wrong room counts, wrong trip_type. If everything looks correct, return {"issues": []}.
Return JSON: {"issues": ["...", "..."]}.
"""


class A8CriticRevise(Approach):
    name = "a8_critic_revise"

    def predict(self, text):
        c = client()
        # 1. Generate
        r1 = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=[{"role": "system", "content": SYSTEM_BASE}, {"role": "user", "content": user_prompt(text)}],
            response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
        )
        draft = json.loads(r1.choices[0].message.content)

        # 2. Critique
        r2 = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=[
                {"role": "system", "content": CRITIC_SYSTEM},
                {"role": "user", "content": f"REQUEST:\n{text}\n\nCANDIDATE:\n{json.dumps(draft, ensure_ascii=False, indent=2)}"},
            ],
            response_format={"type": "json_object"},
        )
        issues = json.loads(r2.choices[0].message.content).get("issues", [])
        if not issues:
            return draft

        # 3. Revise
        r3 = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=[
                {"role": "system", "content": SYSTEM_BASE},
                {"role": "user", "content": user_prompt(text)},
                {"role": "assistant", "content": json.dumps(draft, ensure_ascii=False)},
                {"role": "user", "content": f"A reviewer found these issues, fix them and return a corrected JSON:\n- " + "\n- ".join(issues)},
            ],
            response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
        )
        return json.loads(r3.choices[0].message.content)


approach = A8CriticRevise()
