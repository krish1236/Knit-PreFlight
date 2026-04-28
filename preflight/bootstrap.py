"""Idempotent on-startup bootstrap.

If the demo-data tables are empty (fresh deploy, fresh database), seed
them so the deployed instance has a working demo path immediately
without manual SSH-and-run on Railway. Three independent checks:

  1. Sample surveys seeded?       → preflight.cli seed-samples
  2. Sample reports precomputed?  → preflight.cli precompute-samples
  3. Calibration ever run?        → preflight.cli calibrate

Each phase is independent and idempotent. Failures in one stage don't
block the others. Runs as a background task during FastAPI lifespan
startup so /health stays responsive immediately on cold deploys.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import CalibrationRun, Run
from preflight.db.session import SessionLocal
from preflight.logging import get_logger

logger = get_logger(__name__)


async def _samples_seeded(session: AsyncSession) -> bool:
    result = await session.execute(
        select(func.count()).select_from(Run).where(Run.is_sample.is_(True))
    )
    return (result.scalar() or 0) >= 1


async def _samples_completed(session: AsyncSession) -> bool:
    """Every seeded sample run has a completed status (i.e. report card persisted)."""
    seeded = await session.execute(
        select(func.count()).select_from(Run).where(Run.is_sample.is_(True))
    )
    seeded_n = seeded.scalar() or 0
    if seeded_n == 0:
        return False

    completed = await session.execute(
        select(func.count())
        .select_from(Run)
        .where(Run.is_sample.is_(True), Run.status == "completed")
    )
    return (completed.scalar() or 0) >= seeded_n


async def _calibration_present(session: AsyncSession) -> bool:
    result = await session.execute(select(func.count()).select_from(CalibrationRun))
    return (result.scalar() or 0) >= 1


async def _seed_samples_if_empty() -> None:
    async with SessionLocal() as session:
        if await _samples_seeded(session):
            logger.info("bootstrap.samples_already_seeded")
            return
    logger.info("bootstrap.seeding_samples")
    from preflight.seeds.sample_loader import seed_samples

    async with SessionLocal() as session:
        inserted = await seed_samples(session)
    logger.info("bootstrap.samples_seeded", count=len(inserted))


async def _precompute_samples_if_missing() -> None:
    async with SessionLocal() as session:
        if await _samples_completed(session):
            logger.info("bootstrap.samples_already_precomputed")
            return
    logger.info("bootstrap.precomputing_samples")
    from preflight.seeds.precompute_reports import precompute_all_samples

    async with SessionLocal() as session:
        run_ids = await precompute_all_samples(session)
    logger.info("bootstrap.samples_precomputed", count=len(run_ids))


async def _calibrate_if_missing() -> None:
    async with SessionLocal() as session:
        if await _calibration_present(session):
            logger.info("bootstrap.calibration_already_present")
            return
    logger.info("bootstrap.running_calibration")
    from preflight.calibration.runner import CalibrationConfig, run_calibration

    cfg = CalibrationConfig(
        n_clean_surveys=20,
        n_baseline_personas=300,
        n_sub_swarm=80,
        seed=7,
    )
    async with SessionLocal() as session:
        results = await run_calibration(session, cfg)
    f1_attr = getattr(results, "overall_macro_f1", None)
    f1_value = f1_attr() if callable(f1_attr) else f1_attr
    logger.info("bootstrap.calibration_complete", f1=f1_value)


async def bootstrap_if_empty() -> None:
    """Run sample seed → precompute → calibrate, each gated on its own
    emptiness check. Errors are logged but do not propagate — partial
    bootstraps are fine because each step is idempotent on the next start.
    """
    for step_name, step in [
        ("seed_samples", _seed_samples_if_empty),
        ("precompute_samples", _precompute_samples_if_missing),
        ("calibrate", _calibrate_if_missing),
    ]:
        try:
            await step()
        except Exception as exc:
            logger.exception(
                "bootstrap.step_failed", step=step_name, error=str(exc)
            )


def schedule_bootstrap() -> asyncio.Task[None]:
    """Schedule bootstrap as a fire-and-forget background task.
    Returns the task so the caller can keep a reference (avoiding the
    'task was destroyed but it is pending' RuntimeWarning).
    """
    return asyncio.create_task(bootstrap_if_empty())
