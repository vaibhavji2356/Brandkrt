"""Conservative token and cost estimates for the approved OpenAI models."""

from dataclasses import dataclass
import json
import math
from typing import Any

from .config import AISettings
from .errors import AIConfigurationError
from .prompting import BrandDiscoveryPrompt


# USD per one million tokens. Keep this table explicit so unknown models fail closed.
MODEL_PRICING_USD_PER_MTOK = {
    "gpt-5.6-luna": (1.00, 6.00),
    "gpt-5.6-terra": (2.50, 15.00),
    "gpt-5.6-sol": (5.00, 30.00),
}
CONSERVATIVE_INPUT_PRICE_MULTIPLIER = 1.25


@dataclass(frozen=True)
class CostEstimate:
    prompt_tokens: int
    schema_tokens: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    maximum_attempts: int
    estimated_max_cost_usd: float


def estimate_text_tokens(value: str) -> int:
    """Deliberately conservative heuristic; does not require a tokenizer dependency."""
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


def estimate_request_cost(
    settings: AISettings,
    prompt: BrandDiscoveryPrompt,
    response_schema: dict[str, Any],
) -> CostEstimate:
    prices = MODEL_PRICING_USD_PER_MTOK.get(settings.model)
    if prices is None:
        raise AIConfigurationError("unapproved_model")
    prompt_tokens = estimate_text_tokens(
        json.dumps(prompt.as_messages(), ensure_ascii=False, separators=(",", ":"))
    )
    schema_tokens = estimate_text_tokens(
        json.dumps(response_schema, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )
    input_tokens = prompt_tokens + schema_tokens
    output_tokens = settings.max_output_tokens
    attempts = settings.max_retries + 1
    input_price, output_price = prices
    cost_per_attempt = (
        (input_tokens * input_price * CONSERVATIVE_INPUT_PRICE_MULTIPLIER)
        + (output_tokens * output_price)
    ) / 1_000_000
    return CostEstimate(
        prompt_tokens=prompt_tokens,
        schema_tokens=schema_tokens,
        estimated_input_tokens=input_tokens,
        estimated_output_tokens=output_tokens,
        maximum_attempts=attempts,
        estimated_max_cost_usd=round(cost_per_attempt * attempts, 8),
    )


def calculate_actual_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = MODEL_PRICING_USD_PER_MTOK.get(model)
    if prices is None:
        return 0.0
    input_price, output_price = prices
    return round(
        ((max(0, input_tokens) * input_price) + (max(0, output_tokens) * output_price))
        / 1_000_000,
        8,
    )
