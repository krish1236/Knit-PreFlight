"""Cost-ledger pricing math."""

from preflight.llm.pricing import compute_cost_usd


def test_sonnet_basic_cost() -> None:
    cost = compute_cost_usd(
        model="claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert cost == 3.0


def test_sonnet_cache_savings() -> None:
    full_cost = compute_cost_usd(
        model="claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=0,
    )
    cached_cost = compute_cost_usd(
        model="claude-sonnet-4-6",
        input_tokens=1000,
        output_tokens=0,
        cache_read_tokens=900,
    )
    assert cached_cost < full_cost
    assert cached_cost == (100 * 3.0 + 900 * 0.30) / 1_000_000


def test_unknown_model_returns_zero() -> None:
    assert compute_cost_usd(model="unknown", input_tokens=1000, output_tokens=1000) == 0.0
