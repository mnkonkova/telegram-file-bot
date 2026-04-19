import asyncio
import logging
import os
import time

from bot.config import DATA_PATH

HEARTBEAT_FILE = os.path.join(DATA_PATH, "heartbeat")
HEARTBEAT_INTERVAL = 30.0
HEARTBEAT_STALE_AFTER = 120.0

logger = logging.getLogger(__name__)

_task: asyncio.Task | None = None


def write_heartbeat() -> None:
    os.makedirs(os.path.dirname(HEARTBEAT_FILE), exist_ok=True)
    with open(HEARTBEAT_FILE, "w") as f:
        f.write(str(time.time()))


def is_healthy(now: float | None = None) -> bool:
    if now is None:
        now = time.time()
    try:
        with open(HEARTBEAT_FILE) as f:
            ts = float(f.read().strip())
    except (OSError, ValueError):
        return False
    return (now - ts) < HEARTBEAT_STALE_AFTER


async def _heartbeat_loop() -> None:
    while True:
        try:
            write_heartbeat()
        except Exception:
            logger.exception("Failed to write heartbeat")
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def start_heartbeat() -> None:
    global _task
    write_heartbeat()
    _task = asyncio.create_task(_heartbeat_loop())


async def stop_heartbeat() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except (asyncio.CancelledError, Exception):
            pass
        _task = None
