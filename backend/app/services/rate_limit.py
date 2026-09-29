"""简单限流(进程内 TokenBucket)：缓解滥用/成本失控。

注意：仅在单一进程内有效；多 worker/分布式需换 Redis 版。
"""
import asyncio
import time
from collections import defaultdict

from fastapi import HTTPException


class TokenBucket:
    def __init__(self, capacity: float, refill_per_sec: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill = refill_per_sec
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def take(self) -> bool:
        async with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.refill)
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


_buckets: defaultdict[str, TokenBucket] = defaultdict(
    lambda: TokenBucket(capacity=2, refill_per_sec=1 / 30)  # 每用户默认 2 个瞬时 + 每30s回填1
)


async def check_rate(user_id: str):
    """超限抛 429；否则放行。"""
    if not await _buckets[user_id].take():
        raise HTTPException(429, "请求过于频繁，请稍后再试")