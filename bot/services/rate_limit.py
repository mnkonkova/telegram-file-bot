import time
from dataclasses import dataclass


@dataclass
class Bucket:
    tokens: float
    updated_at: float


class TokenBucket:
    """Per-user token bucket. Admins bypass via `exempt` set.

    Thread/async-safety: CPython dict ops on single event loop are atomic enough
    for this use case; no explicit lock needed.
    """

    def __init__(self, rate_per_sec: float, burst: int, exempt: set[str] | None = None):
        self.rate = rate_per_sec
        self.burst = burst
        self.exempt = {e.lower() for e in (exempt or set())}
        self._buckets: dict[str, Bucket] = {}

    def allow(self, key: str | None) -> bool:
        if not key:
            return False
        key = key.lower()
        if key in self.exempt:
            return True
        now = time.monotonic()
        b = self._buckets.get(key)
        if b is None:
            self._buckets[key] = Bucket(tokens=self.burst - 1, updated_at=now)
            return True
        elapsed = now - b.updated_at
        b.tokens = min(self.burst, b.tokens + elapsed * self.rate)
        b.updated_at = now
        if b.tokens >= 1:
            b.tokens -= 1
            return True
        return False


# Separate buckets: uploads are more expensive (embeddings), asks cheaper.
# Tuned for personal/small-team use. Admins exempt.
from bot.config import ADMIN_USERNAMES

upload_limiter = TokenBucket(rate_per_sec=1 / 30, burst=5, exempt=ADMIN_USERNAMES)
ask_limiter = TokenBucket(rate_per_sec=1 / 10, burst=10, exempt=ADMIN_USERNAMES)
