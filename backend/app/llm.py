"""Async Claude wrapper, plus a bounded-concurrency gather helper for
the document-selection tournament's rounds (corpus_navigation.py). This
project runs inside FastAPI, so concurrency here is asyncio, not the
thread pool the standalone CLI version used.

No embedding call anywhere in this file, or anywhere in this project --
every retrieval decision, at both the document level and the section
level, is a Claude call reasoning over titles and summaries.
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, TypeVar

from anthropic import AsyncAnthropic

from . import config

DEFAULT_MODEL = config.CLAUDE_MODEL
FAST_MODEL = config.CLAUDE_FAST_MODEL

_client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from the environment


@dataclass
class ClaudeCall:
    text: str
    latency_s: float
    input_tokens: int
    output_tokens: int


async def ask_claude(system: str, user: str, max_tokens: int = 500,
                      model: Optional[str] = None) -> ClaudeCall:
    start = time.time()
    resp = await _client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return ClaudeCall(
        text=text,
        latency_s=time.time() - start,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
    )


T = TypeVar("T")
R = TypeVar("R")


async def parallel_map(fn: Callable[[T], Awaitable[R]], items: List[T],
                        max_concurrency: Optional[int] = None) -> List[R]:
    """Runs fn(item) for every item concurrently, bounded by a
    semaphore, preserving item order in the result. Used to fan a
    tournament round's batches out in parallel rather than paying
    their latency one at a time."""
    if len(items) <= 1:
        return [await fn(item) for item in items]

    sem = asyncio.Semaphore(max_concurrency or config.NAV_MAX_CONCURRENCY)

    async def bounded(item: T) -> R:
        async with sem:
            return await fn(item)

    return list(await asyncio.gather(*(bounded(i) for i in items)))
