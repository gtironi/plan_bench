"""Registry of specialized skills loaded from markdown files."""
import os
import re

_SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_skill(path):
    with open(path) as f:
        content = f.read()
    # Extract name from first heading: # Skill: <name>
    name_m = re.search(r"^#\s+Skill:\s+(.+)$", content, re.MULTILINE)
    assert name_m, f"missing '# Skill: ...' in {path}"
    name = name_m.group(1).strip()
    # Extract when_to_use from bold line
    when_m = re.search(r"\*\*When to use:\*\*\s*(.+)", content)
    when_to_use = when_m.group(1).strip() if when_m else ""
    return {"name": name, "when_to_use": when_to_use, "prompt": content}


SKILLS = []
for _fname in sorted(os.listdir(_SKILLS_DIR)):
    if _fname.endswith(".md"):
        SKILLS.append(_load_skill(os.path.join(_SKILLS_DIR, _fname)))

SKILLS_BY_NAME = {s["name"]: s for s in SKILLS}


def catalog():
    """Lightweight list for the router: just name + when_to_use."""
    return [{"name": s["name"], "when_to_use": s["when_to_use"]} for s in SKILLS]
