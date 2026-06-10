"""Token-bucket rate limiter for API protection."""
from __future__ import annotations

import time
import threading
from collections import defaultdict


class RateLimiter:
    """Token-bucket rate limiter.

    Each client (identified by key) has a bucket that refills at a steady
    rate. When a request comes in, a token is consumed. If the bucket is
    empty, the request is rate-limited.
    """

    def __init__(self, rate: float = 10.0, burst: int = 20):
        """
        Args:
            rate: Tokens per second refill rate.
            burst: Maximum bucket capacity (burst size).
        """
        self.rate = rate
        self.burst = burst
        self._buckets: dict[str, tuple[float, float]] = {}  # key → (tokens, last_update)
        self._lock = threading.Lock()

    def acquire(self, key: str, cost: float = 1.0) -> bool:
        """Try to acquire tokens from the bucket.

        Returns True if allowed, False if rate-limited.
        """
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.burst, now))
            # Refill
            elapsed = now - last
            tokens = min(self.burst, tokens + elapsed * self.rate)
            last = now

            if tokens >= cost:
                tokens -= cost
                self._buckets[key] = (tokens, last)
                return True
            else:
                self._buckets[key] = (tokens, last)
                return False

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)

    def status(self, key: str) -> dict:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.burst, now))
            elapsed = now - last
            current = min(self.burst, tokens + elapsed * self.rate)
            return {
                "tokens": round(current, 2),
                "capacity": self.burst,
                "rate_per_sec": self.rate,
            }


# Global instance for middleware use
_global_limiter: RateLimiter | None = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    global _global_limiter
    if _global_limiter is None:
        with _limiter_lock:
            if _global_limiter is None:
                from config.settings import settings
                _global_limiter = RateLimiter(
                    rate=settings.RATE_LIMIT_REQUESTS_PER_SEC,
                    burst=settings.RATE_LIMIT_BURST,
                )
    return _global_limiter


async def rate_limit_middleware(request, call_next):
    """ASGI middleware that applies rate limiting.

    Uses client IP as the bucket key. Returns 429 when limit exceeded.
    """
    from fastapi.responses import JSONResponse

    # Skip health endpoint
    if request.url.path == "/health":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    limiter = get_rate_limiter()

    if not limiter.acquire(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down."},
            headers={"Retry-After": "5"},
        )

    return await call_next(request)
