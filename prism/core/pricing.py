"""Built-in pricing table for popular models (USD per 1K tokens).

Used to estimate cost from token usage. Models not present in the table are
billed at zero so callers never crash on an unknown model name.
"""

from __future__ import annotations

# (prompt_price_per_1k, completion_price_per_1k)
PRICING: dict = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "gpt-3.5-turbo": (0.0005, 0.0015),
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-haiku": (0.00025, 0.00125),
}


def estimate(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    if model in PRICING:
        ip, oc = PRICING[model]
        return prompt_tokens / 1000 * ip + completion_tokens / 1000 * oc
    return 0.0
