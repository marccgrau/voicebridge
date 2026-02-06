"""Process cleanup utilities for graceful shutdown."""

import asyncio
import logging
import signal
import sys
from collections.abc import Callable

logger = logging.getLogger(__name__)


def setup_signal_handlers(cleanup_callback: Callable[[], None]) -> None:
    """Set up signal handlers for graceful shutdown.

    Args:
        cleanup_callback: Async function to call on shutdown
    """

    def signal_handler(signum: int, _frame) -> None:
        """Handle termination signals."""
        sig_name = signal.Signals(signum).name
        logger.info("Received signal %s, initiating graceful shutdown...", sig_name)

        # Run cleanup in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_shutdown(cleanup_callback))
            else:
                loop.run_until_complete(_shutdown(cleanup_callback))
        except Exception as e:
            logger.error("Error during signal handler cleanup: %s", e)
        finally:
            sys.exit(0)

    # Register handlers for common termination signals
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # kill command
    if sys.platform != "win32":
        signal.signal(signal.SIGHUP, signal_handler)  # Terminal closed


async def _shutdown(cleanup_callback: Callable[[], None]) -> None:
    """Execute shutdown cleanup.

    Args:
        cleanup_callback: Async function to call
    """
    try:
        await asyncio.wait_for(cleanup_callback(), timeout=30.0)
        logger.info("Cleanup completed successfully")
    except TimeoutError:
        logger.warning("Cleanup timed out after 30s")
    except Exception as e:
        logger.error("Cleanup failed: %s", e)
