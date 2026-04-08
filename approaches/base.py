"""Approach interface."""
import json
import re


class Approach:
    name = "base"

    def predict(self, text: str) -> dict:
        raise NotImplementedError


def extract_json(s: str) -> dict:
    """Extract a JSON object from a possibly noisy string."""
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    # If there's a fenced block anywhere:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # Otherwise find first { ... last }
    i, j = s.find("{"), s.rfind("}")
    assert i != -1 and j != -1, f"no JSON object in:\n{s}"
    return json.loads(s[i : j + 1])
