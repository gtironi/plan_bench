"""Reflexion: generate, self-reflect on possible errors, regenerate. Up to K iterations."""
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from schema import PLAN_JSON_SCHEMA
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach

K = 3
REFLECT_SYSTEM = """You are reflecting on your own previous attempt at extracting a travel plan.
Look at the original request and your candidate JSON. Without consulting any ground truth,
list every aspect that might be wrong, ambiguous, or missing. Consider: forgotten travelers,
wrong cabin, missing return leg, wrong IATA mapping, wrong dates, wrong room count.
If you are confident the plan is correct, return {"done": true, "notes": []}.
Otherwise return {"done": false, "notes": ["...", "..."]}.
"""


class A10Reflexion(Approach):
    name = "a10_reflexion"

    def predict(self, text):
        c = client()
        memory = []
        plan = None
        for _ in range(K):
            sys_msg = SYSTEM_BASE
            if memory:
                sys_msg += "\n\nLessons from your previous attempts:\n- " + "\n- ".join(memory)
            r = c.chat.completions.create(
                model=MODEL_MAIN,
                messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_prompt(text)}],
                response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
            )
            plan = json.loads(r.choices[0].message.content)

            rr = c.chat.completions.create(
                model=MODEL_MAIN,
                messages=[
                    {"role": "system", "content": REFLECT_SYSTEM},
                    {"role": "user", "content": f"REQUEST:\n{text}\n\nCANDIDATE:\n{json.dumps(plan, ensure_ascii=False, indent=2)}"},
                ],
                response_format={"type": "json_object"},
            )
            ref = json.loads(rr.choices[0].message.content)
            if ref.get("done"):
                break
            memory.extend(ref.get("notes", []))
        return plan


approach = A10Reflexion()
