"""ACS PUMS person-level loader.

Source: US Census Bureau, ACS 1-year PUMS, person-level file.
Reference: https://www.census.gov/programs-surveys/acs/microdata.html

The on-disk format is a filtered parquet at data/pums/acs_pums.parquet with
columns:
  AGEP   - age in years
  SEX    - 1=male, 2=female
  SCHL   - educational attainment code
  PINCP  - personal income (USD)
  ST     - state FIPS
  RAC1P  - race recode
  MAR    - marital status
  PWGTP  - person weight (used for representative sampling)

The prep script (scripts/prepare_pums.py) downloads the raw file from Census,
filters to relevant columns and US adults, and writes the parquet.

If the parquet is not present, a synthetic-but-realistic fallback is generated
in-memory so the persona engine can be exercised in tests and local dev. The
fallback is clearly logged so production code paths cannot silently use it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from preflight.logging import get_logger
from preflight.persona.schema import AudienceConstraints

logger = get_logger(__name__)

PUMS_PATH = Path("data/pums/acs_pums.parquet")
SYNTHETIC_N = 50_000

SCHL_TO_LABEL = {
    1: "less_than_hs", 2: "less_than_hs", 3: "less_than_hs", 4: "less_than_hs",
    5: "less_than_hs", 6: "less_than_hs", 7: "less_than_hs", 8: "less_than_hs",
    9: "less_than_hs", 10: "less_than_hs", 11: "less_than_hs", 12: "less_than_hs",
    13: "less_than_hs", 14: "less_than_hs", 15: "less_than_hs",
    16: "hs", 17: "hs",
    18: "some_college", 19: "some_college", 20: "some_college",
    21: "college",
    22: "graduate", 23: "graduate", 24: "graduate",
}

EDU_RANK = {
    "less_than_hs": 0, "hs": 1, "some_college": 2, "college": 3, "graduate": 4
}

EDU_MIN_THRESHOLD = {
    "any": 0, "hs": 1, "some_college": 2, "college": 3, "graduate": 4
}

RAC1P_LABELS = {
    1: "white", 2: "black", 3: "native", 4: "native", 5: "native",
    6: "asian", 7: "pacific_islander", 8: "other", 9: "multi",
}

MAR_LABELS = {1: "married", 2: "widowed", 3: "divorced", 4: "separated", 5: "never_married"}

STATE_FIPS_TO_USPS = {
    1: "AL", 2: "AK", 4: "AZ", 5: "AR", 6: "CA", 8: "CO", 9: "CT", 10: "DE",
    11: "DC", 12: "FL", 13: "GA", 15: "HI", 16: "ID", 17: "IL", 18: "IN",
    19: "IA", 20: "KS", 21: "KY", 22: "LA", 23: "ME", 24: "MD", 25: "MA",
    26: "MI", 27: "MN", 28: "MS", 29: "MO", 30: "MT", 31: "NE", 32: "NV",
    33: "NH", 34: "NJ", 35: "NM", 36: "NY", 37: "NC", 38: "ND", 39: "OH",
    40: "OK", 41: "OR", 42: "PA", 44: "RI", 45: "SC", 46: "SD", 47: "TN",
    48: "TX", 49: "UT", 50: "VT", 51: "VA", 53: "WA", 54: "WV", 55: "WI",
    56: "WY",
}


@lru_cache(maxsize=1)
def load_pums() -> pd.DataFrame:
    """Load PUMS parquet (cached). Falls back to synthetic data with a loud warning."""
    if PUMS_PATH.exists():
        df = pd.read_parquet(PUMS_PATH)
        logger.info("pums.loaded", path=str(PUMS_PATH), rows=len(df))
        return df

    logger.warning(
        "pums.synthetic_fallback",
        reason="parquet missing; generating synthetic dataset",
        path=str(PUMS_PATH),
        rows=SYNTHETIC_N,
        action="run scripts/prepare_pums.py to install the real PUMS slice",
    )
    return _generate_synthetic_pums(n=SYNTHETIC_N, seed=42)


def filter_by_audience(df: pd.DataFrame, audience: AudienceConstraints) -> pd.DataFrame:
    out = df.copy()

    out = out[(out["AGEP"] >= audience.age_range.min) & (out["AGEP"] <= audience.age_range.max)]

    if audience.genders and "any" not in audience.genders:
        sex_codes = []
        if "male" in audience.genders:
            sex_codes.append(1)
        if "female" in audience.genders:
            sex_codes.append(2)
        out = out[out["SEX"].isin(sex_codes)]

    if audience.income_range.min is not None:
        out = out[out["PINCP"].fillna(0) >= audience.income_range.min]
    if audience.income_range.max is not None:
        out = out[out["PINCP"].fillna(0) <= audience.income_range.max]

    if audience.education_min != "any":
        threshold = EDU_MIN_THRESHOLD[audience.education_min]
        out = out[out["SCHL"].map(SCHL_TO_LABEL).map(EDU_RANK) >= threshold]

    if audience.geo.states:
        usps_to_fips = {v: k for k, v in STATE_FIPS_TO_USPS.items()}
        fips = [usps_to_fips[s] for s in audience.geo.states if s in usps_to_fips]
        if fips:
            out = out[out["ST"].isin(fips)]

    return out


def weighted_sample(df: pd.DataFrame, n: int, seed: int = 42) -> pd.DataFrame:
    if df.empty:
        raise ValueError("cannot sample from empty dataframe")
    if "PWGTP" not in df.columns:
        raise ValueError("dataframe missing PWGTP column")

    rng = np.random.default_rng(seed)
    weights = df["PWGTP"].astype(float).to_numpy()
    weights = weights / weights.sum()
    n = min(n, len(df))
    idx = rng.choice(len(df), size=n, replace=False, p=weights)
    return df.iloc[idx].reset_index(drop=True)


def _generate_synthetic_pums(n: int, seed: int) -> pd.DataFrame:
    """Synthetic dataset preserving rough joint distributions for dev / tests.

    Income and education are correlated (r >~ 0.4); age is roughly uniform 18-80.
    Not for production use — the real PUMS file is the calibration ground truth.
    """
    rng = np.random.default_rng(seed)

    age = rng.integers(low=18, high=80, size=n)
    sex = rng.choice([1, 2], size=n, p=[0.49, 0.51])

    schl_choices = list(SCHL_TO_LABEL.keys())
    schl = rng.choice(schl_choices, size=n)

    edu_rank = np.array([EDU_RANK[SCHL_TO_LABEL[s]] for s in schl])
    base_income = 25_000 + edu_rank * 18_000 + rng.normal(0, 12_000, size=n)
    age_factor = np.where(age < 30, 0.7, np.where(age < 50, 1.0, 0.9))
    income = np.clip(base_income * age_factor, 0, 500_000).astype(int)

    state_fips = rng.choice(list(STATE_FIPS_TO_USPS.keys()), size=n)
    rac1p = rng.choice([1, 2, 3, 6, 8, 9], size=n, p=[0.60, 0.13, 0.02, 0.06, 0.10, 0.09])
    mar = rng.choice([1, 2, 3, 4, 5], size=n, p=[0.50, 0.06, 0.10, 0.02, 0.32])

    pwgtp = rng.integers(low=10, high=300, size=n)

    return pd.DataFrame(
        {
            "AGEP": age,
            "SEX": sex,
            "SCHL": schl,
            "PINCP": income,
            "ST": state_fips,
            "RAC1P": rac1p,
            "MAR": mar,
            "PWGTP": pwgtp,
        }
    )
