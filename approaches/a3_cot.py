"""Chain-of-thought: reason in text, then emit final JSON."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach, extract_json

COT_INSTRUCTIONS = """
First reason step by step under a heading "## Reasoning":
1. List every traveler mentioned and assign them stable ids.
2. List every flight leg with origin, destination, dates, and which travelers.
3. List every hotel stay with city, dates, and which travelers.
4. Decide trip_type based on the legs.

Then under a heading "## Final JSON" emit a single fenced ```json ... ``` block containing the plan. The JSON must match the schema strictly.
"""


class A3CoT(Approach):
    name = "a3_cot"

    def predict(self, text):
        c = client()
        resp = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=[
                {"role": "system", "content": SYSTEM_BASE + COT_INSTRUCTIONS},
                {"role": "user", "content": user_prompt(text)},
            ],
        )
        return extract_json(resp.choices[0].message.content)


approach = A3CoT()
