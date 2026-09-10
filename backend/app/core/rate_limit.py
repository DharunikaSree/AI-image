"""
In-memory sliding-window rate limiter for FastAPI.
Zero external dependencies, thread-safe, and fully configurable via environment variables.
"""
import time
from collections import defaultdict, deque
from threading import Lock
from fastapi import HTTPException, Request, status

from app.core.config import get_settings

settings = get_settings()


class InMemoryRateLimiter:
    """Sliding-window rate limiter keyed by client IP or identifier."""

    def __init__(self):
        self._lock = Lock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def is_rate_limited(self, key: str, max_requests: int, window_seconds: int = 60) -> tuple[bool, int]:
        """
        Returns (is_limited: bool, retry_after_seconds: int).
        """
        if not settings.RATE_LIMIT_ENABLED or max_requests <= 0:
            return False, 0

        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            history = self._requests[key]

            # Evict timestamps older than the sliding window
            while history and history[0] <= window_start:
                history.popleft()

            if len(history) >= max_requests:
                earliest = history[0]
                retry_after = max(1, int(window_seconds - (now - earliest)))
                return True, retry_after

            history.append(now)
            return False, 0

    def reset(self):
        """Clears all stored rate limit histories (used in tests)."""
        with self._lock:
            self._requests.clear()


limiter = InMemoryRateLimiter()


def get_client_ip(request: Request) -> str:
    """Extract client IP safely from request headers or client socket."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def rate_limit(limit_type: str = "global"):
    """
    FastAPI dependency factory to enforce rate limits.
    limit_type options: 'search', 'auth', 'global'
    """
    async def dependency(request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return

        client_ip = get_client_ip(request)
        key = f"{limit_type}:{client_ip}"

        if limit_type == "search":
            max_req = settings.RATE_LIMIT_SEARCH_PER_MINUTE
        elif limit_type == "auth":
            max_req = settings.RATE_LIMIT_AUTH_PER_MINUTE
        else:
            max_req = settings.RATE_LIMIT_GLOBAL_PER_MINUTE

        is_limited, retry_after = limiter.is_rate_limited(key, max_req, window_seconds=60)
        if is_limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {limit_type} operations. Please try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
