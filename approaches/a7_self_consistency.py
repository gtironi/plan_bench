"""Self-consistency: N amostras do mesmo schema, voto por conteúdo de passo."""
import copy
import json
import sys
import os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import client, MODEL_MAIN
from schema import PLAN_JSON_SCHEMA, _step_key
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach

N = 5


def _relinearize_steps(steps):
    """step_id, depends_on, next_step em cadeia 0→1→… (como o dataset)."""
    for i, s in enumerate(steps):
        s["step_id"] = i
        s["depends_on"] = [] if i == 0 else [i - 1]
        s["next_step"] = i + 1 if i < len(steps) - 1 else None
    return steps


def _vote(samples):
    """Voto por chave canónica de passo (schema._step_key); inclui passos com >= ceil(N/2) amostras."""
    if not samples:
        return {"steps": []}

    threshold = (len(samples) + 1) // 2

    # Quantas amostras distintas contêm pelo menos um passo com esta chave
    key_support = Counter()
    key_to_steps = {}
    for si, plan in enumerate(samples):
        steps = plan.get("steps") or []
        keys_here = {_step_key(s) for s in steps if isinstance(s, dict) and s.get("action")}
        for k in keys_here:
            key_support[k] += 1
        for s in steps:
            if not isinstance(s, dict) or not s.get("action"):
                continue
            k = _step_key(s)
            key_to_steps.setdefault(k, []).append((si, s))

    winning_keys = [k for k, c in key_support.items() if c >= threshold]
    # Ordem estável: voos antes de hotéis por tipo, depois tuplo
    winning_keys.sort()

    chosen = []
    for k in winning_keys:
        candidates = key_to_steps[k]
        blob_counts = Counter(json.dumps(c[1], sort_keys=True, ensure_ascii=False) for c in candidates)
        best_blob = blob_counts.most_common(1)[0][0]
        representative = next(c[1] for c in candidates if json.dumps(c[1], sort_keys=True, ensure_ascii=False) == best_blob)
        chosen.append(copy.deepcopy(representative))

    _relinearize_steps(chosen)
    return {"steps": chosen}


class A7SelfConsistency(Approach):
    name = "a7_self_consistency"

    def predict(self, text):
        c = client()
        samples = []
        for _ in range(N):
            r = c.chat.completions.create(
                model=MODEL_MAIN,
                messages=[
                    {"role": "system", "content": SYSTEM_BASE},
                    {"role": "user", "content": user_prompt(text)},
                ],
                response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
                temperature=0.7,
            )
            samples.append(json.loads(r.choices[0].message.content))
        return _vote(samples)


approach = A7SelfConsistency()
