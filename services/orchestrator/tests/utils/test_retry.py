"""Tests for retry utility."""

import asyncio

import pytest

from src.utils.retry import retry_async


class TestRetryAsync:
    """Tests for retry_async function."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        """Test that function succeeds on first attempt without retries."""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_async(success_func, max_retries=3)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_after_retries(self):
        """Test that function eventually succeeds after some failures."""
        call_count = 0

        async def eventual_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result = await retry_async(eventual_success, max_retries=5, base_delay=0.01)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_fails_after_max_retries(self):
        """Test that function raises exception after all retries exhausted."""
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            await retry_async(always_fails, max_retries=3, base_delay=0.01)

        assert call_count == 4  # Initial attempt + 3 retries

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test that exponential backoff increases delay correctly."""
        delays = []
        call_count = 0

        async def track_delays():
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                delays.append(asyncio.get_event_loop().time())
            if call_count < 4:
                raise ValueError("Fail")
            return "success"

        start_time = asyncio.get_event_loop().time()
        await retry_async(track_delays, max_retries=3, base_delay=0.1, exponential=True)
        end_time = asyncio.get_event_loop().time()

        # Should have taken at least 0.1 + 0.2 + 0.4 = 0.7 seconds
        total_time = end_time - start_time
        assert total_time >= 0.7
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_linear_backoff(self):
        """Test that linear backoff uses constant delay."""
        call_count = 0

        async def track_calls():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Fail")
            return "success"

        start_time = asyncio.get_event_loop().time()
        await retry_async(track_calls, max_retries=3, base_delay=0.1, exponential=False)
        end_time = asyncio.get_event_loop().time()

        # Should have taken at least 0.1 + 0.1 = 0.2 seconds
        total_time = end_time - start_time
        assert total_time >= 0.2
        assert total_time < 0.5  # But not exponential time
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test that on_retry callback is invoked correctly."""
        call_count = 0
        retry_log = []

        def on_retry(attempt: int, exc: Exception):
            retry_log.append((attempt, str(exc)))

        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError(f"Fail {call_count}")
            return "success"

        result = await retry_async(fails_twice, max_retries=3, base_delay=0.01, on_retry=on_retry)

        assert result == "success"
        assert call_count == 3
        assert len(retry_log) == 2
        assert retry_log[0] == (1, "Fail 1")
        assert retry_log[1] == (2, "Fail 2")

    @pytest.mark.asyncio
    async def test_zero_retries(self):
        """Test that max_retries=0 means no retries."""
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Fail")

        with pytest.raises(ValueError):
            await retry_async(always_fails, max_retries=0, base_delay=0.01)

        assert call_count == 1  # Only initial attempt, no retries
