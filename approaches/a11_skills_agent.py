"""Agent that picks 1+ skills from the markdown catalog and applies them to extract the plan."""
import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from schema import PLAN_JSON_SCHEMA
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach
from approaches.skills import SKILLS_BY_NAME, catalog

ROUTER_SYSTEM = """You are a router for a corporate travel extraction system.
Given a travel request and a catalog of skills, choose the ONE skill that best matches.
If the request combines patterns (e.g. converging group + multi-city), return up to 3 skill names ordered by relevance.

Return JSON: {"skills": ["skill_name", ...]}
"""


class A11SkillsAgent(Approach):
    name = "a11_skills_agent"

    def predict(self, text):
        c = client()

        # 1. Router picks skills from catalog.
        r = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM},
                {"role": "user", "content": f"REQUEST:\n{text}\n\nCATALOG:\n{json.dumps(catalog(), ensure_ascii=False, indent=2)}"},
            ],
            response_format={"type": "json_object"},
        )
        picked = json.loads(r.choices[0].message.content).get("skills", [])
        picked = [p for p in picked if p in SKILLS_BY_NAME]
        if not picked:
            picked = [catalog()[0]["name"]]

        # 2. Stack the full markdown of each chosen skill on top of the base system prompt.
        stacked = SYSTEM_BASE + "\n\n---\n\n## Active skill(s)\n\n"
        for name in picked:
            stacked += SKILLS_BY_NAME[name]["prompt"] + "\n\n"

        # 3. Single extraction call with structured output.
        r2 = c.chat.completions.create(
            model=MODEL_MAIN,
            messages=[
                {"role": "system", "content": stacked},
                {"role": "user", "content": user_prompt(text)},
            ],
            response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
        )
        return json.loads(r2.choices[0].message.content)


approach = A11SkillsAgent()
