"""Few-shot with retrieval.

Retrieval pool = full dataset MINUS the items currently being evaluated.
The run_eval.py calls `approach.set_eval_ids(eval_ids)` before the loop
so the approach never retrieves an item that is in the eval split.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from config import client, MODEL_MAIN, MODEL_EMBED
from schema import PLAN_JSON_SCHEMA
from prompts.shared import SYSTEM_BASE, user_prompt
from approaches.base import Approach

DATASET = os.path.join(os.path.dirname(__file__), "..", "dataset", "out", "dataset.jsonl")
INDEX   = os.path.join(os.path.dirname(__file__), "..", "dataset", "out", "embeddings.npz")
K = 3


def _load_dataset():
    with open(DATASET) as f:
        return [json.loads(l) for l in f]


def build_index():
    data = _load_dataset()
    c = client()
    vecs, ids = [], []
    for d in data:
        resp = c.embeddings.create(model=MODEL_EMBED, input=d["text"])
        vecs.append(resp.data[0].embedding)
        ids.append(d.get("id", ""))
        print(f"embed {d.get('id','?')} ok")
    arr = np.array(vecs, dtype=np.float32)
    arr /= np.linalg.norm(arr, axis=1, keepdims=True)
    np.savez(INDEX, vectors=arr, ids=np.array(ids))
    print(f"wrote -> {INDEX}")


def _embed(text):
    c = client()
    v = np.array(c.embeddings.create(model=MODEL_EMBED, input=text).data[0].embedding, dtype=np.float32)
    v /= np.linalg.norm(v)
    return v


class A5FewshotRetrieval(Approach):
    name = "a5_fewshot_retrieval"

    def __init__(self):
        z = np.load(INDEX, allow_pickle=True)
        self.vecs = z["vectors"]
        self.ids  = list(z["ids"])
        self.data = {d.get("id", ""): d for d in _load_dataset()}
        # Set of ids to exclude from retrieval (populated by run_eval).
        self._excluded: set = set()

    def set_eval_ids(self, ids):
        """Call this before the eval loop with the ids of items being evaluated."""
        self._excluded = set(ids)

    def _topk(self, text, current_id=None):
        q = _embed(text)
        sims = self.vecs @ q
        order = np.argsort(-sims)
        picked = []
        for idx in order:
            did = self.ids[idx]
            # Exclude: the current item itself + the whole eval split
            if did == current_id or did in self._excluded:
                continue
            picked.append(did)
            if len(picked) >= K:
                break
        return picked

    def predict(self, text, exclude_id=None):
        picks = self._topk(text, current_id=exclude_id)
        c = client()
        msgs = [{"role": "system", "content": SYSTEM_BASE}]
        for pid in picks:
            ex = self.data[pid]
            msgs.append({"role": "user",      "content": user_prompt(ex["text"])})
            msgs.append({"role": "assistant", "content": json.dumps(ex["plan"], ensure_ascii=False)})
        msgs.append({"role": "user", "content": user_prompt(text)})
        resp = c.chat.completions.create(
            model=MODEL_MAIN, messages=msgs,
            response_format={"type": "json_schema", "json_schema": PLAN_JSON_SCHEMA},
        )
        return json.loads(resp.choices[0].message.content)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-index", action="store_true")
    args = ap.parse_args()
    if args.build_index:
        build_index()
else:
    approach = A5FewshotRetrieval() if os.path.exists(INDEX) else None
