"""Anthropic client wrapper.

Adds:
  - prompt caching support (system message marked with cache_control)
  - rolling-window circuit breaker
  - token-bucket rate limit (Tier 4 default: 4000 RPM ~ 67 RPS)
  - exponential-backoff retry on 429 / 5xx
  - per-call cost ledger (LLMCall row)
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from anthropic import APIError, AsyncAnthropic, RateLimitError
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from preflight.config import get_settings
from preflight.db.models import LLMCall
from preflight.llm.circuit_breaker import CircuitBreaker
from preflight.llm.pricing import compute_cost_usd
from preflight.llm.rate_limiter import TokenBucket
from preflight.logging import get_logger

logger = get_logger(__name__)


Purpose = Literal["paraphrase_gen", "probe_response", "equivalence_judge", "calibration"]


@dataclass
class CallResult:
    text: str
    raw: Any
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float


class AnthropicClient:
    """Thin wrapper around AsyncAnthropic enforcing rate limit, circuit, and ledger."""

    def __init__(
        self,
        rate_per_sec: float = 50.0,
        circuit_window: int = 30,
        max_concurrency: int = 60,
    ) -> None:
        self._settings = get_settings()
        self._sdk = AsyncAnthropic(api_key=self._settings.anthropic_api_key)
        self._rate = TokenBucket(rate_per_sec=rate_per_sec)
        self._circuit = CircuitBreaker(window_size=circuit_window)
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def message(
        self,
        *,
        model: str,
        system: str | list[dict[str, Any]],
        user: str | list[dict[str, Any]],
        purpose: Purpose,
        max_tokens: int = 256,
        temperature: float = 0.7,
        cache_system: bool = True,
        run_id: uuid.UUID | None = None,
        session: AsyncSession | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
    ) -> CallResult:
        """Send a message; return parsed text + usage telemetry.

        cache_system=True wraps the system string in a cache_control block so it is
        eligible for ephemeral prompt caching across calls within the cache TTL.
        """
        system_param = self._build_system(system, cache_system=cache_system)
        user_param = self._build_user(user)

        self._circuit.before_call()
        await self._rate.acquire()

        async with self._semaphore:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(5),
                wait=wait_exponential_jitter(initial=1, max=30),
                retry=retry_if_exception_type((RateLimitError, APIError)),
                reraise=True,
            ):
                with attempt:
                    try:
                        kwargs: dict[str, Any] = {
                            "model": model,
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            "system": system_param,
                            "messages": [{"role": "user", "content": user_param}],
                        }
                        if tools:
                            kwargs["tools"] = tools
                        if tool_choice:
                            kwargs["tool_choice"] = tool_choice

                        response = await self._sdk.messages.create(**kwargs)
                        self._circuit.record_success()
                    except (RateLimitError, APIError):
                        self._circuit.record_failure()
                        raise

        text = self._extract_text(response)
        usage = response.usage
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0

        cost = compute_cost_usd(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
        )

        if session is not None:
            session.add(
                LLMCall(
                    run_id=run_id,
                    model=model,
                    purpose=purpose,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                    cost_usd=cost,
                )
            )

        return CallResult(
            text=text,
            raw=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost_usd=cost,
        )

    @staticmethod
    def _build_system(system: str | list[dict[str, Any]], *, cache_system: bool) -> Any:
        if isinstance(system, list):
            return system
        if cache_system:
            return [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        return system

    @staticmethod
    def _build_user(user: str | list[dict[str, Any]]) -> Any:
        if isinstance(user, list):
            return user
        return [{"type": "text", "text": user}]

    @staticmethod
    def _extract_text(response: Any) -> str:
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""


_client: AnthropicClient | None = None


def get_client() -> AnthropicClient:
    global _client
    if _client is None:
        _client = AnthropicClient()
    return _client
