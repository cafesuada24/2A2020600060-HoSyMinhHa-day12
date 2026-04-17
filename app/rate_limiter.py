"""Rate limiter."""

import collections
import time

from fastapi import HTTPException


class RateLimiter:
    """Sliding window Rate Limiter."""

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> None:
        """Initialize rate limiter.

        Args:
            max_requests: maximum number of requests in window.
            window_seconds: period in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_history: dict[str, collections.deque] = collections.defaultdict(
            collections.deque,
        )
        self.total_checks = 0
        self.total_blocks = 0

    def allow_request(self, user_id: str = 'default') -> dict:
        """Check if user exceed rate limit.

        Raise:
            HTTPExecption 429 if exceeded
        """
        self.total_checks += 1

        now = time.time()
        history = self.user_history[user_id]

        while history and history[0] < now - self.window_seconds:
            history.popleft()

        reset_at = int(now) + self.window_seconds

        if len(history) >= self.max_requests:
            self.total_blocks += 1
            wait_seconds = int(self.window_seconds - (now - history[0])) + 1
            raise HTTPException(
                status_code=429,
                detail={
                    'error': 'Rate limit exceeded',
                    'limit': self.max_requests,
                    'window_seconds': self.window_seconds,
                    'retry_after_seconds': wait_seconds,
                },
                headers={
                    'X-RateLimit-Limit': str(self.max_requests),
                    'X-RateLimit-Remaining': '0',
                    'X-RateLimit-Reset': str(reset_at),
                    'Retry-After': str(wait_seconds),
                },
            )

        remaining = self.max_requests - len(history)
        history.append(now)
        return {
            'limit': self.max_requests,
            'remaining': remaining - 1,
            'reset_at': reset_at,
        }

    def get_stats(self, user_id: str) -> dict[str, object]:
        """Get user usage stats."""
        now = time.time()
        history = self.user_history[user_id]
        active = sum(1 for t in history if t >= now - self.window_seconds)
        return {
            "requests_in_window": active,
            "limit": self.max_requests,
            "remaining": max(0, self.max_requests - active),
        }


# Test
if __name__ == '__main__':
    rl = RateLimiter(max_requests=3, window_seconds=5)
    for i in range(5):
        r = rl.allow_request('test_user')
        print(
            f'  Request {i + 1}: {r["limit"]=}, {r["remaining"]=}, {r["reset_at"]=}s',
        )
    del rl
