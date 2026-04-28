"""Lock the duplicate-sample-row failure modes.

Earlier deploys hit MultipleResultsFound three times in a row in three
different places. Each time the fix was the same shape: never use
scalar_one_or_none on a query that can legally return multiple rows
in production. This test pins that contract for the precompute path.
"""

from __future__ import annotations

import inspect

from preflight.routes import samples as samples_route
from preflight.seeds import precompute_reports
from preflight.seeds import sample_loader


def _source(fn: object) -> str:
    return inspect.getsource(fn)  # type: ignore[arg-type]


def test_precompute_all_samples_does_not_use_scalar_one_or_none() -> None:
    """precompute_all_samples must tolerate multiple is_sample rows per
    survey_id (left over from earlier route bugs that created duplicates).
    Using scalar_one_or_none crashes on >1 row.
    """
    src = _source(precompute_reports.precompute_all_samples)
    assert "scalar_one_or_none" not in src, (
        "precompute_all_samples must use .scalars().first() on a "
        ".limit(1) query so duplicate seed rows do not crash bootstrap"
    )
    assert ".order_by" in src, (
        "precompute_all_samples must order results so the same row is "
        "picked across deploys (canonical seed = oldest)"
    )


def test_seed_samples_does_not_use_scalar_one_or_none() -> None:
    src = _source(sample_loader.seed_samples)
    assert "scalar_one_or_none" not in src, (
        "seed_samples must use .first() so the gate check works when "
        "earlier deploys left duplicate is_sample rows"
    )


def test_run_sample_route_does_not_use_scalar_one_or_none() -> None:
    src = _source(samples_route.run_sample)
    assert "scalar_one_or_none" not in src, (
        "run_sample route must use .scalars().first() on the cached and "
        "in-flight queries so duplicate sample rows do not crash a click"
    )


def test_run_sample_route_reuses_in_flight_runs() -> None:
    """Locking the bug fix: clicking a sample button while bootstrap
    precompute is still running must NOT create another pending row.
    The route must look up an existing in-flight run and return its id.
    """
    src = _source(samples_route.run_sample)
    assert "in_flight_statuses" in src, (
        "run_sample must check for existing in-flight sample runs "
        "before creating a new one"
    )
    for status in ("pending", "personas_ready", "probing", "stats_running"):
        assert status in src, (
            f"in_flight_statuses must include {status!r} so a run already "
            "in that state is reused rather than duplicated"
        )
