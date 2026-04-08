# OpenAI model pricing (USD per 1M tokens, as of 2026-04-08)
# Source: manually recorded from OpenAI pricing page
# Format: model -> (input, cached_input, output)  — None if not available

PRICING = {
    "gpt-5.2":       (1.75,   0.175,  14.00),
    "gpt-5.2-pro":   (21.00,  None,  168.00),
    "gpt-5.1":       (1.25,   0.125,  10.00),
    "gpt-5":         (1.25,   0.125,  10.00),
    "gpt-5-mini":    (0.25,   0.025,   2.00),
    "gpt-5-nano":    (0.05,   0.005,   0.40),
    "gpt-5-pro":     (15.00,  None,  120.00),
    "gpt-4.1":       (2.00,   0.50,    8.00),
    "gpt-4.1-mini":  (0.40,   0.10,    1.60),
    "gpt-4.1-nano":  (0.10,   0.025,   0.40),
    "gpt-4o":        (2.50,   1.25,   10.00),
    "gpt-4o-mini":   (0.15,   0.075,   0.60),
    "o4-mini":       (1.10,   0.275,   4.40),
    "o3":            (2.00,   0.50,    8.00),
    "o3-mini":       (1.10,   0.55,    4.40),
    "o3-pro":        (20.00,  None,   80.00),
    "o1":            (15.00,  7.50,   60.00),
    "o1-mini":       (1.10,   0.55,    4.40),
    "o1-pro":        (150.00, None,  600.00),
    "gpt-3.5-turbo": (0.50,   None,    1.50),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    """Return estimated cost in USD."""
    p = PRICING[model]
    input_price, cached_price, output_price = p
    regular_input = input_tokens - cached_tokens
    total = (regular_input / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)
    if cached_tokens and cached_price:
        total += cached_tokens / 1_000_000 * cached_price
    return total
