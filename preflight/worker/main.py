"""Worker entrypoint — long-running consumer of the job stream.

Run via:
    python -m preflight.worker.main

Loops forever:
  1. XREADGROUP one message
  2. Dispatch to handler
  3. XACK on success; XADD-to-DLQ + XACK on terminal failure
"""

from __future__ import annotations

import asyncio
import signal

from preflight.logging import configure_logging, get_logger
from preflight.worker.dispatcher import dispatch
from preflight.worker.queue import MAX_ATTEMPTS, JobQueue

logger = get_logger(__name__)


class WorkerLoop:
    def __init__(self) -> None:
        self._queue = JobQueue()
        self._stopping = asyncio.Event()

    async def run(self) -> None:
        await self._queue.ensure_group()
        logger.info("worker.started")
        while not self._stopping.is_set():
            entry = await self._queue.consume_one(block_ms=2000)
            if entry is None:
                continue
            message_id, payload = entry
            try:
                await dispatch(payload, self._queue)
                await self._queue.ack(message_id)
            except Exception as exc:
                if payload.attempt >= MAX_ATTEMPTS:
                    await self._queue.dead_letter(message_id, payload, str(exc))
                else:
                    payload_retry = payload.model_copy(update={"attempt": payload.attempt + 1})
                    await self._queue.enqueue(
                        job_type=payload_retry.job_type,
                        run_id=payload_retry.run_id,
                        args=payload_retry.args,
                        attempt=payload_retry.attempt,
                    )
                    await self._queue.ack(message_id)
                    logger.warning(
                        "worker.retry_scheduled",
                        run_id=str(payload.run_id),
                        attempt=payload_retry.attempt,
                    )
        await self._queue.close()
        logger.info("worker.stopped")

    def request_stop(self) -> None:
        self._stopping.set()


async def amain() -> None:
    configure_logging()
    worker = WorkerLoop()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.request_stop)

    await worker.run()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
