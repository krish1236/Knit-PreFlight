"""Command-line entrypoints for Pre-Flight workflows.

Subcommands:
  generate-pool   Generate a persona pool to JSON (no DB required)
  spot-check      Render N personas with full prompt template for visual review
  seed-samples    Insert sample-survey runs from seeds/ into the database
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from preflight.persona.pool_generator import generate_pool_in_memory
from preflight.persona.prompt_template import render_persona_prompt
from preflight.persona.schema import (
    AgeRange,
    AudienceConstraints,
    GeoConstraint,
    IncomeRange,
    ResponseStyleConfig,
)


def _build_audience(
    age_min: int, age_max: int, gender: str, income_min: int | None, education_min: str,
    states: list[str],
) -> AudienceConstraints:
    return AudienceConstraints(
        age_range=AgeRange(min=age_min, max=age_max),
        genders=[gender] if gender != "any" else ["any"],
        income_range=IncomeRange(min=income_min, max=None),
        education_min=education_min,  # type: ignore[arg-type]
        geo=GeoConstraint(country="US", states=states),
    )


def cmd_generate_pool(args: argparse.Namespace) -> int:
    audience = _build_audience(
        age_min=args.age_min,
        age_max=args.age_max,
        gender=args.gender,
        income_min=args.income_min,
        education_min=args.education_min,
        states=args.states or [],
    )
    personas = generate_pool_in_memory(
        audience=audience,
        style_config=ResponseStyleConfig(),
        n=args.n,
        seed=args.seed,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([p.model_dump(mode="json") for p in personas], indent=2)
    )
    print(f"wrote {len(personas)} personas to {out_path}")
    return 0


def cmd_spot_check(args: argparse.Namespace) -> int:
    audience = _build_audience(
        age_min=args.age_min,
        age_max=args.age_max,
        gender=args.gender,
        income_min=args.income_min,
        education_min=args.education_min,
        states=args.states or [],
    )
    personas = generate_pool_in_memory(
        audience=audience,
        style_config=ResponseStyleConfig(),
        n=args.n,
        seed=args.seed,
    )
    for p in personas:
        print("=" * 70)
        print(f"id: {p.id}")
        print(f"demographic: {p.demographic.model_dump()}")
        print(f"response_style: {p.response_style.model_dump()}")
        print()
        print(render_persona_prompt(p))
        print()
    return 0


def _add_audience_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--age-min", type=int, default=18)
    parser.add_argument("--age-max", type=int, default=65)
    parser.add_argument(
        "--gender", choices=["any", "male", "female"], default="any"
    )
    parser.add_argument("--income-min", type=int, default=None)
    parser.add_argument(
        "--education-min",
        choices=["any", "hs", "some_college", "college", "graduate"],
        default="any",
    )
    parser.add_argument(
        "--states", nargs="*", default=None, help="USPS codes, e.g., NY CA TX"
    )
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)


def cmd_seed_samples(args: argparse.Namespace) -> int:
    from preflight.db.session import SessionLocal
    from preflight.seeds.sample_loader import seed_samples

    async def _run() -> list:
        async with SessionLocal() as session:
            return await seed_samples(session)

    inserted = asyncio.run(_run())
    print(f"seeded {len(inserted)} sample run(s)")
    for run_id in inserted:
        print(f"  - {run_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preflight")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pool = sub.add_parser("generate-pool", help="Generate a persona pool to JSON")
    _add_audience_args(p_pool)
    p_pool.add_argument("--out", default="pool.json")
    p_pool.set_defaults(func=cmd_generate_pool)

    p_check = sub.add_parser(
        "spot-check", help="Render personas with full prompt for visual review"
    )
    _add_audience_args(p_check)
    p_check.set_defaults(func=cmd_spot_check, n=5)

    p_seed = sub.add_parser(
        "seed-samples", help="Insert sample surveys from seeds/ into the runs table"
    )
    p_seed.set_defaults(func=cmd_seed_samples)

    args = parser.parse_args(argv)
    return args.func(args)  # type: ignore[no-any-return]


if __name__ == "__main__":
    sys.exit(main())
