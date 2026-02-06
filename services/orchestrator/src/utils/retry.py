"""Async retry utility with exponential backoff."""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_async(
    func: Callable[[], Any],
    max_retries: int,
    base_delay: float = 0.5,
    exponential: bool = True,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    """Retry an async function with exponential backoff.

    Args:
        func: Async function to retry (no arguments)
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
        exponential: If True, use exponential backoff (delay * 2^attempt)
        on_retry: Optional callback called on each retry with (attempt, exception)

    Returns:
        Result of the function call

    Raises:
        The last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return await asyncio.to_thread(func)
        except Exception as e:
            last_exception = e

            if attempt >= max_retries:
                # No more retries left
                break

            # Calculate delay
            delay = base_delay * 2**attempt if exponential else base_delay

            # Call retry callback if provided
            if on_retry:
                on_retry(attempt + 1, e)
            else:
                logger.warning(
                    "Retry attempt %d/%d failed: %s (retrying in %.2fs)",
                    attempt + 1,
                    max_retries,
                    e,
                    delay,
                )

            await asyncio.sleep(delay)

    # All retries exhausted
    logger.error("All %d retry attempts failed", max_retries)
    raise last_exception  # type: ignore
