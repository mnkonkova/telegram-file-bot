import asyncio
import os
import time


def test_write_heartbeat_creates_file(tmp_paths):
    from bot.services import heartbeat as hb

    hb.write_heartbeat()
    assert os.path.exists(hb.HEARTBEAT_FILE)
    ts = float(open(hb.HEARTBEAT_FILE).read())
    assert abs(ts - time.time()) < 5


def test_is_healthy_missing_file(tmp_paths):
    from bot.services import heartbeat as hb

    assert hb.is_healthy() is False


def test_is_healthy_fresh(tmp_paths):
    from bot.services import heartbeat as hb

    hb.write_heartbeat()
    assert hb.is_healthy() is True


def test_is_healthy_stale(tmp_paths):
    from bot.services import heartbeat as hb

    with open(hb.HEARTBEAT_FILE, "w") as f:
        f.write(str(time.time() - hb.HEARTBEAT_STALE_AFTER - 1))
    assert hb.is_healthy() is False


def test_is_healthy_corrupt(tmp_paths):
    from bot.services import heartbeat as hb

    with open(hb.HEARTBEAT_FILE, "w") as f:
        f.write("not-a-number")
    assert hb.is_healthy() is False


async def test_heartbeat_loop_writes_file(tmp_paths, monkeypatch):
    from bot.services import heartbeat as hb

    monkeypatch.setattr(hb, "HEARTBEAT_INTERVAL", 0.05)

    await hb.start_heartbeat()
    await asyncio.sleep(0.12)
    assert hb.is_healthy()
    await hb.stop_heartbeat()
