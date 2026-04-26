"""Redis Streams job queue.

Single stream `preflight:jobs` with consumer group `workers`. Each worker
process registers a unique consumer name and pulls jobs via XREADGROUP.

Idempotency: each job carries (run_id, job_type, attempt) and handlers are
expected to be safe to re-execute. Failed jobs are NACKed via XADD to a
dead-letter stream after max_attempts.
"""

from __future__ import annotations

import json
import socket
import uuid
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from preflight.config import get_settings
from preflight.logging import get_logger
from preflight.schemas.run import JobPayload, JobType

logger = get_logger(__name__)

STREAM_KEY = "preflight:jobs"
DLQ_KEY = "preflight:jobs:dlq"
GROUP = "workers"
MAX_ATTEMPTS = 3


def _consumer_name() -> str:
    return f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


class JobQueue:
    """Async wrapper over redis-py streams API."""

    def __init__(self, redis: Redis | None = None, consumer: str | None = None) -> None:
        self._redis = redis or Redis.from_url(get_settings().redis_url, decode_responses=True)
        self._consumer = consumer or _consumer_name()

    async def ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(
                name=STREAM_KEY, groupname=GROUP, id="0", mkstream=True
            )
            logger.info("queue.group_created", stream=STREAM_KEY, group=GROUP)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def enqueue(
        self,
        job_type: JobType,
        run_id: uuid.UUID,
        args: dict[str, Any] | None = None,
        attempt: int = 1,
    ) -> str:
        payload = JobPayload(
            job_type=job_type, run_id=run_id, attempt=attempt, args=args or {}
        )
        message_id = await self._redis.xadd(
            STREAM_KEY,
            {"payload": payload.model_dump_json()},
        )
        logger.info(
            "queue.enqueued",
            job_type=job_type,
            run_id=str(run_id),
            message_id=message_id,
        )
        return message_id

    async def consume_one(self, block_ms: int = 5000) -> tuple[str, JobPayload] | None:
        result = await self._redis.xreadgroup(
            groupname=GROUP,
            consumername=self._consumer,
            streams={STREAM_KEY: ">"},
            count=1,
            block=block_ms,
        )
        if not result:
            return None
        _, entries = result[0]
        if not entries:
            return None
        message_id, fields = entries[0]
        payload = JobPayload.model_validate_json(fields["payload"])
        return message_id, payload

    async def ack(self, message_id: str) -> None:
        await self._redis.xack(STREAM_KEY, GROUP, message_id)

    async def dead_letter(self, message_id: str, payload: JobPayload, reason: str) -> None:
        await self._redis.xadd(
            DLQ_KEY,
            {
                "payload": payload.model_dump_json(),
                "reason": reason,
                "original_id": message_id,
            },
        )
        await self._redis.xack(STREAM_KEY, GROUP, message_id)
        logger.error(
            "queue.dead_lettered",
            job_type=payload.job_type,
            run_id=str(payload.run_id),
            reason=reason,
        )

    async def close(self) -> None:
        await self._redis.aclose()


def encode_args(args: dict[str, Any]) -> str:
    return json.dumps(args, separators=(",", ":"), default=str)
