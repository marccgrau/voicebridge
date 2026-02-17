"""Asynchronous transcript persistence helpers for PCC."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _FlushRequest:
    future: asyncio.Future[None]


_SHUTDOWN_SENTINEL = object()


class TranscriptPersistenceWorker:
    """Persist transcript segments asynchronously in background batches.

    The worker is intentionally decoupled from the transcript hot path:
    transcript frames are queued immediately and database writes happen in
    a background task.
    """

    def __init__(
        self,
        *,
        session_id: str,
        supabase_url: str,
        service_role_key: str,
        queue_max_size: int = 2000,
        batch_size: int = 20,
        flush_interval_seconds: float = 0.25,
        request_timeout_seconds: float = 5.0,
        max_retries: int = 3,
        retry_base_delay_seconds: float = 0.25,
        client: httpx.AsyncClient | None = None,
    ):
        self._session_id = session_id
        self._insert_url = f"{supabase_url.rstrip('/')}/rest/v1/transcript_segments"
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

        self._batch_size = max(batch_size, 1)
        self._flush_interval_seconds = max(flush_interval_seconds, 0.01)
        self._request_timeout_seconds = max(request_timeout_seconds, 0.1)
        self._max_retries = max(max_retries, 0)
        self._retry_base_delay_seconds = max(retry_base_delay_seconds, 0.01)

        self._queue: asyncio.Queue[dict[str, Any] | _FlushRequest | object] = asyncio.Queue(
            maxsize=max(queue_max_size, 1)
        )
        self._worker_task: asyncio.Task[None] | None = None
        self._start_lock = asyncio.Lock()

        self._client = client
        self._owns_client = client is None
        self._closed = False
        self._dropped_count = 0

    @classmethod
    def from_env(cls, session_id: str) -> TranscriptPersistenceWorker | None:
        """Create a worker from environment variables.

        Returns ``None`` when Supabase credentials are not configured.
        """

        supabase_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not supabase_url or not service_role_key:
            logger.info(
                "[session=%s] Transcript DB persistence disabled: missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY",
                session_id,
            )
            return None

        return cls(
            session_id=session_id,
            supabase_url=supabase_url,
            service_role_key=service_role_key,
        )

    async def start(self) -> None:
        """Start the background persistence worker."""
        if self._closed:
            return

        async with self._start_lock:
            if self._worker_task is not None:
                return

            if self._client is None:
                self._client = httpx.AsyncClient(timeout=self._request_timeout_seconds)

            self._worker_task = asyncio.create_task(
                self._run(),
                name=f"transcript-persistence-{self._session_id}",
            )

    def enqueue(self, row: dict[str, Any]) -> None:
        """Queue a transcript row for asynchronous persistence.

        This method is intentionally non-blocking to avoid adding latency to
        the transcript pipeline.
        """
        if self._closed or self._worker_task is None:
            return

        if self._worker_task.done():
            logger.warning(
                "[session=%s] Transcript persistence worker already stopped; dropping segment",
                self._session_id,
            )
            return

        try:
            self._queue.put_nowait(row)
        except asyncio.QueueFull:
            self._dropped_count += 1
            if self._dropped_count == 1 or self._dropped_count % 25 == 0:
                logger.warning(
                    "[session=%s] Transcript queue full; dropped %d segment(s)",
                    self._session_id,
                    self._dropped_count,
                )

    async def flush(self, timeout_seconds: float | None = 3.0) -> None:
        """Wait until all currently queued transcript rows are persisted."""
        if self._worker_task is None or self._worker_task.done():
            return

        loop = asyncio.get_running_loop()
        future: asyncio.Future[None] = loop.create_future()
        await self._queue.put(_FlushRequest(future=future))

        try:
            if timeout_seconds is None:
                await future
            else:
                await asyncio.wait_for(future, timeout=timeout_seconds)
        except TimeoutError:
            logger.warning(
                "[session=%s] Timed out waiting for transcript queue flush",
                self._session_id,
            )

    async def shutdown(self, timeout_seconds: float = 5.0) -> None:
        """Flush and stop the worker task."""
        if self._closed:
            return
        self._closed = True

        task = self._worker_task
        if task is None:
            if self._client and self._owns_client:
                await self._client.aclose()
            return

        if not task.done():
            await self.flush(timeout_seconds=max(timeout_seconds - 0.5, 0.5))
            await self._queue.put(_SHUTDOWN_SENTINEL)

        try:
            await asyncio.wait_for(task, timeout=timeout_seconds)
        except TimeoutError:
            logger.warning(
                "[session=%s] Transcript worker shutdown timed out; cancelling task",
                self._session_id,
            )
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        finally:
            self._worker_task = None
            if self._client and self._owns_client:
                await self._client.aclose()
                self._client = None

        if self._dropped_count:
            logger.warning(
                "[session=%s] Transcript worker dropped %d segment(s) due to backpressure",
                self._session_id,
                self._dropped_count,
            )

    async def _run(self) -> None:
        if self._client is None:
            raise RuntimeError("TranscriptPersistenceWorker started without HTTP client")

        batch: list[dict[str, Any]] = []

        while True:
            try:
                item = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=self._flush_interval_seconds,
                )
            except TimeoutError:
                if batch:
                    await self._persist_batch(batch)
                    batch.clear()
                continue

            if item is _SHUTDOWN_SENTINEL:
                self._queue.task_done()
                if batch:
                    await self._persist_batch(batch)
                    batch.clear()
                break

            if isinstance(item, _FlushRequest):
                self._queue.task_done()
                if batch:
                    await self._persist_batch(batch)
                    batch.clear()
                if not item.future.done():
                    item.future.set_result(None)
                continue

            batch.append(item)
            self._queue.task_done()

            if len(batch) >= self._batch_size:
                await self._persist_batch(batch)
                batch.clear()

    async def _persist_batch(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return

        for attempt in range(self._max_retries + 1):
            try:
                await self._post_rows(rows)
                return
            except Exception as exc:  # noqa: BLE001
                if attempt >= self._max_retries:
                    logger.error(
                        "[session=%s] Failed to persist transcript batch (%d rows): %s",
                        self._session_id,
                        len(rows),
                        exc,
                    )
                    return

                delay = self._retry_base_delay_seconds * (2**attempt)
                logger.warning(
                    "[session=%s] Transcript persist retry %d/%d in %.2fs: %s",
                    self._session_id,
                    attempt + 1,
                    self._max_retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)

    async def _post_rows(self, rows: list[dict[str, Any]]) -> None:
        if self._client is None:
            raise RuntimeError("TranscriptPersistenceWorker has no HTTP client")

        response = await self._client.post(
            self._insert_url,
            headers=self._headers,
            json=rows,
            timeout=self._request_timeout_seconds,
        )

        if response.status_code >= 300:
            body = response.text
            raise RuntimeError(f"Supabase insert failed ({response.status_code}): {body}")
