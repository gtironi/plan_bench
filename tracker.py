"""Real-time usage tracker. Wraps the OpenAI client so every call reports
actual input/output tokens and accumulates cost. Enforces a hard budget."""
import sys
from pricing import PRICING, PRICING_FALLBACK


class BudgetExceeded(Exception):
    pass


class Tracker:
    def __init__(self):
        self.budget_usd = float("inf")
        self.spent_usd = 0.0
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_tokens = 0
        self.by_model = {}  # model -> {calls, in, out, cached, cost}

    def set_budget(self, usd: float):
        self.budget_usd = usd

    def record(self, model: str, usage):
        """usage is the .usage object from an OpenAI response."""
        in_tok = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", 0) or 0
        cached = 0
        details = getattr(usage, "prompt_tokens_details", None) or getattr(usage, "input_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0

        cost = self._cost(model, in_tok, out_tok, cached)
        self.calls += 1
        self.input_tokens += in_tok
        self.output_tokens += out_tok
        self.cached_tokens += cached
        self.spent_usd += cost

        m = self.by_model.setdefault(model, {"calls": 0, "in": 0, "out": 0, "cached": 0, "cost": 0.0})
        m["calls"] += 1
        m["in"] += in_tok
        m["out"] += out_tok
        m["cached"] += cached
        m["cost"] += cost

        if self.spent_usd >= self.budget_usd:
            raise BudgetExceeded(
                f"budget exhausted: ${self.spent_usd:.4f} >= ${self.budget_usd:.2f}"
            )

    @staticmethod
    def _cost(model, in_tok, out_tok, cached_tok):
        p = PRICING.get(model, PRICING_FALLBACK)
        in_price, cached_price, out_price = p
        regular_in = in_tok - cached_tok
        total = (regular_in / 1_000_000 * in_price) + (out_tok / 1_000_000 * out_price)
        if cached_tok and cached_price:
            total += cached_tok / 1_000_000 * cached_price
        return total

    def print_status(self, prefix=""):
        pct = (self.spent_usd / self.budget_usd * 100) if self.budget_usd != float("inf") else 0
        print(
            f"{prefix}spent=${self.spent_usd:.4f}/{self.budget_usd:.2f} ({pct:.1f}%) "
            f"calls={self.calls} in={self.input_tokens} out={self.output_tokens} cached={self.cached_tokens}"
        )

    def print_summary(self):
        print("\n" + "=" * 70)
        print("USAGE SUMMARY")
        print("=" * 70)
        print(f"  {'model':<20} {'calls':>6} {'in':>10} {'out':>10} {'cached':>8} {'cost USD':>12}")
        for model, v in sorted(self.by_model.items()):
            print(f"  {model:<20} {v['calls']:>6} {v['in']:>10,} {v['out']:>10,} {v['cached']:>8,} ${v['cost']:>11.4f}")
        print(f"  {'TOTAL':<20} {self.calls:>6} {self.input_tokens:>10,} {self.output_tokens:>10,} {self.cached_tokens:>8,} ${self.spent_usd:>11.4f}")
        print("=" * 70)


TRACKER = Tracker()


def wrap_client(raw_client):
    """Monkey-patch a client so every .chat.completions.create / .responses.create
    records usage on TRACKER and enforces the budget."""
    orig_chat = raw_client.chat.completions.create

    def chat_create(*args, **kwargs):
        resp = orig_chat(*args, **kwargs)
        model = kwargs.get("model") or getattr(resp, "model", "unknown")
        if getattr(resp, "usage", None) is not None:
            TRACKER.record(model, resp.usage)
        return resp

    raw_client.chat.completions.create = chat_create

    # Also wrap responses.create if used
    if hasattr(raw_client, "responses"):
        orig_resp = raw_client.responses.create

        def resp_create(*args, **kwargs):
            resp = orig_resp(*args, **kwargs)
            model = kwargs.get("model") or getattr(resp, "model", "unknown")
            if getattr(resp, "usage", None) is not None:
                TRACKER.record(model, resp.usage)
            return resp

        raw_client.responses.create = resp_create

    # Embeddings — track too
    if hasattr(raw_client, "embeddings"):
        orig_emb = raw_client.embeddings.create

        def emb_create(*args, **kwargs):
            resp = orig_emb(*args, **kwargs)
            model = kwargs.get("model") or getattr(resp, "model", "unknown")
            if getattr(resp, "usage", None) is not None:
                TRACKER.record(model, resp.usage)
            return resp

        raw_client.embeddings.create = emb_create

    return raw_client
