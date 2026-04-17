import collections
import time

from fastapi import HTTPException


class RateLimiter:
    """Rate Limiter that supports both in-memory and Redis (Stateless)."""

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        redis_client=None,
    ) -> None:
        """Initialize rate limiter.

        Args:
            max_requests: maximum number of requests in window.
            window_seconds: period in seconds
            redis_client: Optional redis client for stateless operation.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.redis = redis_client

        # Fallback for in-memory
        if not self.redis:

            self.user_history: dict[str, collections.deque] = collections.defaultdict(
                collections.deque,
            )

    def allow_request(self, user_id: str = 'default') -> dict:
        """Check if user exceeds rate limit.

        Raise:
            HTTPException 429 if exceeded
        """
        now = time.time()
        reset_at = int(now) + self.window_seconds

        if self.redis:
            # Redis implementation using Sorted Set for Sliding Window
            key = f'rate_limit:{user_id}'
            pipeline = self.redis.pipeline()
            # Remove old requests
            pipeline.zremrangebyscore(key, 0, now - self.window_seconds)
            # Count current requests
            pipeline.zcard(key)
            # Add new request
            pipeline.zadd(key, {str(now): now})
            # Set expiry for the key
            pipeline.expire(key, self.window_seconds + 5)

            _, count, _, _ = pipeline.execute()

            if count >= self.max_requests:
                # We already added the request, but we exceed limit.
                # Ideally we check before adding, but for simplicity:
                retry_after = self.window_seconds
                raise HTTPException(
                    status_code=429,
                    detail={
                        'error': 'Rate limit exceeded (Redis)',
                        'limit': self.max_requests,
                        'retry_after_seconds': retry_after,
                    },
                    headers={'Retry-After': str(retry_after)},
                )
            return {
                'limit': self.max_requests,
                'remaining': self.max_requests - count - 1,
                'reset_at': reset_at,
            }
        # In-memory implementation
        history = self.user_history[user_id]
        while history and history[0] < now - self.window_seconds:
            history.popleft()

        if len(history) >= self.max_requests:
            wait_seconds = int(self.window_seconds - (now - history[0])) + 1
            raise HTTPException(
                status_code=429,
                detail={
                    'error': 'Rate limit exceeded (In-memory)',
                    'limit': self.max_requests,
                    'retry_after_seconds': wait_seconds,
                },
                headers={'Retry-After': str(wait_seconds)},
            )

        history.append(now)
        return {
            'limit': self.max_requests,
            'remaining': self.max_requests - len(history),
            'reset_at': reset_at,
        }

    def get_stats(self, user_id: str) -> dict:
        if self.redis:
            now = time.time()
            count = self.redis.zcount(
                f'rate_limit:{user_id}', now - self.window_seconds, now
            )
            return {
                'requests_in_window': count,
                'limit': self.max_requests,
                'remaining': max(0, self.max_requests - count),
            }
        now = time.time()
        history = self.user_history[user_id]
        active = sum(1 for t in history if t >= now - self.window_seconds)
        return {
            'requests_in_window': active,
            'limit': self.max_requests,
            'remaining': max(0, self.max_requests - active),
        }
