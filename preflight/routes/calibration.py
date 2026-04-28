"""Calibration dashboard endpoints.

Phase 5 fills these with real F1 numbers from the defect-injection
calibration harness. Until then, the endpoint reports an honest
'calibration_pending' state so the frontend can render a placeholder
without fabricating metrics.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from preflight.db.models import CalibrationRun
from preflight.db.session import get_session

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.get("")
async def get_calibration(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(CalibrationRun).order_by(desc(CalibrationRun.completed_at)).limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None:
        return {
            "status": "calibration_pending",
            "f1_overall": None,
            "f1_per_class": {},
            "n_surveys": 0,
            "benchmark": "not yet run; the calibration harness lands in Phase 5",
            "last_run": None,
            "history": [],
        }

    history_rows = (
        await session.execute(
            select(CalibrationRun).order_by(desc(CalibrationRun.completed_at)).limit(20)
        )
    ).scalars().all()

    return {
        "status": "ok",
        "f1_overall": float(latest.f1_overall),
        "f1_per_class": latest.f1_per_class,
        "n_surveys": latest.n_surveys,
        "benchmark": "PMC 48-bias-type catalog × 3 severity levels on Pew/ANES/GSS instruments",
        "last_run": {
            "git_sha": latest.git_sha,
            "completed_at": latest.completed_at.isoformat(),
        },
        "history": [
            {
                "git_sha": r.git_sha,
                "f1_overall": float(r.f1_overall),
                "completed_at": r.completed_at.isoformat(),
            }
            for r in history_rows
        ],
    }
