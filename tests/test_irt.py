"""IRT 2PL fitter — synthetic-data sanity tests."""

from __future__ import annotations

import numpy as np

from preflight.stats.analyzers.irt import _fit_2pl, _neg_log_likelihood_2pl, _sigmoid


def test_sigmoid_handles_extremes() -> None:
    assert _sigmoid(np.array([-1000.0])).item() < 1e-9
    assert 1 - _sigmoid(np.array([1000.0])).item() < 1e-9


def _simulate_2pl(
    n_persons: int, true_a: np.ndarray, true_b: np.ndarray, seed: int = 0
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    theta = rng.normal(scale=1.0, size=n_persons)
    n_items = len(true_a)
    p = _sigmoid(true_a[None, :] * (theta[:, None] - true_b[None, :]))
    return (rng.uniform(size=(n_persons, n_items)) < p).astype(float)


def test_fit_recovers_relative_discrimination_ranking() -> None:
    """The fit should rank items in the same order as their true discrimination.

    Joint 2PL MLE is non-convex and under-determined at small N×items. We use
    Spearman correlation between true and fitted discrimination as the
    quality criterion — perfect recovery is NOT expected on synthetic data,
    but the rank order should be preserved.
    """
    from scipy.stats import spearmanr

    rng = np.random.default_rng(42)
    n_persons = 1500
    true_a = np.array([0.2, 0.4, 0.6, 0.9, 1.2, 1.5, 1.8, 2.0])  # 8 items, monotone
    true_b = rng.normal(scale=0.5, size=len(true_a))
    matrix = _simulate_2pl(n_persons=n_persons, true_a=true_a, true_b=true_b, seed=1)

    fitted, _converged = _fit_2pl(matrix)
    fitted_a = fitted[n_persons : n_persons + len(true_a)]

    rho = float(spearmanr(true_a, fitted_a).statistic)
    assert rho >= 0.6, f"rank correlation too low: {rho:.2f}; fitted={fitted_a}"


def test_neg_log_likelihood_finite_on_random_input() -> None:
    rng = np.random.default_rng(0)
    matrix = (rng.uniform(size=(50, 5)) > 0.5).astype(float)
    params = rng.normal(size=50 + 5 + 5)
    nll = _neg_log_likelihood_2pl(params, matrix, 50, 5)
    assert np.isfinite(nll)
