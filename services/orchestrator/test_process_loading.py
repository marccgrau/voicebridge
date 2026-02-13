#!/usr/bin/env python3
"""Quick test to verify process catalog loading."""

import asyncio
import logging

# Add src to path
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.flows.process_flow import load_process_catalog


async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    process_path = Path(__file__).parent / "process_content"
    logger.info(f"Loading processes from: {process_path}")

    processes = await load_process_catalog(process_path, logger)

    logger.info(f"✅ Loaded {len(processes)} processes:")
    for key, proc in processes.items():
        logger.info(f"  - {key}: {proc.name} ({len(proc.steps)} steps)")
        logger.info(f"    Intents: {', '.join(proc.intents)}")
        logger.info(f"    Steps: {', '.join([s.label for s in proc.steps])}")
        logger.info("")


if __name__ == "__main__":
    asyncio.run(main())
