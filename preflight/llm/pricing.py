"""Per-token pricing for cost ledger. Update when Anthropic pricing changes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """Prices in USD per million tokens."""

    input_per_mtok: float
    output_per_mtok: float
    cache_write_per_mtok: float
    cache_read_per_mtok: float


PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-4-6": ModelPricing(
        input_per_mtok=3.0,
        output_per_mtok=15.0,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),
    "claude-haiku-4-5-20251001": ModelPricing(
        input_per_mtok=0.80,
        output_per_mtok=4.0,
        cache_write_per_mtok=1.0,
        cache_read_per_mtok=0.08,
    ),
}


def compute_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    pricing = PRICING.get(model)
    if pricing is None:
        return 0.0

    uncached_input = max(0, input_tokens - cache_read_tokens - cache_write_tokens)
    return (
        uncached_input * pricing.input_per_mtok
        + cache_read_tokens * pricing.cache_read_per_mtok
        + cache_write_tokens * pricing.cache_write_per_mtok
        + output_tokens * pricing.output_per_mtok
    ) / 1_000_000
