import pytest


def test_allows_within_burst():
    from bot.services.rate_limit import TokenBucket

    tb = TokenBucket(rate_per_sec=0.0, burst=3)
    assert tb.allow("user") is True
    assert tb.allow("user") is True
    assert tb.allow("user") is True
    assert tb.allow("user") is False


def test_separate_users():
    from bot.services.rate_limit import TokenBucket

    tb = TokenBucket(rate_per_sec=0.0, burst=1)
    assert tb.allow("alice") is True
    assert tb.allow("bob") is True
    assert tb.allow("alice") is False


def test_exempt_bypasses():
    from bot.services.rate_limit import TokenBucket

    tb = TokenBucket(rate_per_sec=0.0, burst=1, exempt={"admin"})
    for _ in range(10):
        assert tb.allow("admin") is True


def test_case_insensitive_exempt():
    from bot.services.rate_limit import TokenBucket

    tb = TokenBucket(rate_per_sec=0.0, burst=1, exempt={"Admin"})
    assert tb.allow("ADMIN") is True
    assert tb.allow("ADMIN") is True


def test_empty_key_denied():
    from bot.services.rate_limit import TokenBucket

    tb = TokenBucket(rate_per_sec=1.0, burst=10)
    assert tb.allow(None) is False
    assert tb.allow("") is False


def test_refill_over_time(monkeypatch):
    from bot.services import rate_limit as rl

    tb = rl.TokenBucket(rate_per_sec=10.0, burst=1)

    now = [100.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: now[0])

    assert tb.allow("u") is True
    assert tb.allow("u") is False
    now[0] += 0.11  # 1.1 tokens refilled
    assert tb.allow("u") is True
