"""Tests for asynchronous transcript persistence worker."""

from __future__ import annotations

import json

import httpx
import pytest

from src.transcript_persistence import TranscriptPersistenceWorker


def _make_row(text: str) -> dict[str, object]:
    return {
        "session_id": "test-session",
        "speaker": "customer",
        "text": text,
        "is_final": True,
        "ts": "2026-02-17T10:00:00Z",
    }


@pytest.mark.asyncio
async def test_worker_batches_rows_before_insert() -> None:
    payloads: list[list[dict[str, object]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(status_code=201)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    worker = TranscriptPersistenceWorker(
        session_id="test-session",
        supabase_url="https://example.supabase.co",
        service_role_key="test-key",
        batch_size=2,
        flush_interval_seconds=30.0,
        client=client,
    )

    await worker.start()
    worker.enqueue(_make_row("hello"))
    worker.enqueue(_make_row("need help"))

    await worker.flush(timeout_seconds=1.0)

    assert len(payloads) == 1
    assert len(payloads[0]) == 2
    assert payloads[0][0]["text"] == "hello"
    assert payloads[0][1]["text"] == "need help"

    await worker.shutdown()
    await client.aclose()


@pytest.mark.asyncio
async def test_worker_retries_failed_batch() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(status_code=500, text="temporary failure")
        return httpx.Response(status_code=201)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    worker = TranscriptPersistenceWorker(
        session_id="test-session",
        supabase_url="https://example.supabase.co",
        service_role_key="test-key",
        batch_size=1,
        max_retries=1,
        retry_base_delay_seconds=0.01,
        client=client,
    )

    await worker.start()
    worker.enqueue(_make_row("retry this"))
    await worker.flush(timeout_seconds=1.0)

    assert attempts == 2

    await worker.shutdown()
    await client.aclose()


def test_worker_from_env_returns_none_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("NEXT_PUBLIC_SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    worker = TranscriptPersistenceWorker.from_env("test-session")

    assert worker is None
