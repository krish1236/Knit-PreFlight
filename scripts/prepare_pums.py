"""Prepare a working ACS PUMS slice from the Census Bureau download.

Run once before live demos. Output: data/pums/acs_pums.parquet (~5MB).

Source: ACS 1-year PUMS person-level file, downloaded from
  https://www.census.gov/programs-surveys/acs/microdata/access.html

Usage:
    1. Download psam_pusa.csv (or any ACS 1-year person CSV) from Census.
    2. Place at data/pums/raw/psam_pusa.csv (path is gitignored).
    3. python scripts/prepare_pums.py

The script:
  - Reads the raw CSV in chunks (raw is hundreds of MB)
  - Filters to US adults 18-80 with non-null PWGTP
  - Keeps only the columns the persona engine needs
  - Writes the filtered parquet
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

KEEP_COLUMNS = ["AGEP", "SEX", "SCHL", "PINCP", "ST", "RAC1P", "MAR", "PWGTP"]
RAW_PATH = Path("data/pums/raw/psam_pusa.csv")
OUT_PATH = Path("data/pums/acs_pums.parquet")


def prepare() -> None:
    if not RAW_PATH.exists():
        print(f"raw PUMS file not found at {RAW_PATH}", file=sys.stderr)
        print(
            "download psam_pusa.csv from "
            "https://www.census.gov/programs-surveys/acs/microdata/access.html",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"reading {RAW_PATH} in chunks...")
    chunks = []
    for chunk in pd.read_csv(RAW_PATH, usecols=KEEP_COLUMNS, chunksize=200_000, low_memory=False):
        chunk = chunk.dropna(subset=["AGEP", "PWGTP"])
        chunk = chunk[(chunk["AGEP"] >= 18) & (chunk["AGEP"] <= 80)]
        chunks.append(chunk)

    df = pd.concat(chunks, ignore_index=True)

    for col in ["AGEP", "SEX", "SCHL", "ST", "RAC1P", "MAR", "PWGTP"]:
        df[col] = df[col].astype("int32")
    df["PINCP"] = df["PINCP"].astype("float32")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, compression="zstd")
    print(f"wrote {len(df):,} rows to {OUT_PATH} ({OUT_PATH.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    prepare()
