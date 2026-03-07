"""Rate Limiter - per-caller rate limiting with token bucket and backoff.

Implements:
- Token bucket algorithm for smooth rate limiting
- Per-caller tracking
- Exponential backoff recommendation on rejection
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter."""
    tokens_per_second: float = 10.0     # Refill rate
    max_tokens: int = 20                # Bucket capacity (burst allowance)
    backoff_base: float = 1.0           # Base backoff in seconds
    backoff_max: float = 60.0           # Max backoff in seconds
    backoff_multiplier: float = 2.0     # Exponential multiplier


@dataclass
class _Bucket:
    """Internal token bucket state."""
    tokens: float
    max_tokens: int
    last_refill: float = field(default_factory=time.time)
    consecutive_rejections: int = 0


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    retry_after: float = 0.0       # Suggested wait time in seconds
    remaining_tokens: int = 0


class RateLimiter:
    """Per-caller token bucket rate limiter."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self._config = config or RateLimitConfig()
        # {caller_id: _Bucket}
        self._buckets: Dict[str, _Bucket] = {}

    def check(self, caller_id: str, tokens: int = 1) -> RateLimitResult:
        """Check if caller can proceed. Does NOT consume tokens."""
        bucket = self._get_bucket(caller_id)
        self._refill(bucket)
        if bucket.tokens >= tokens:
            return RateLimitResult(
                allowed=True,
                remaining_tokens=int(bucket.tokens),
            )
        wait = (tokens - bucket.tokens) / self._config.tokens_per_second
        return RateLimitResult(
            allowed=False,
            retry_after=round(wait, 2),
            remaining_tokens=int(bucket.tokens),
        )

    def acquire(self, caller_id: str, tokens: int = 1) -> RateLimitResult:
        """Try to consume tokens. Returns result with backoff if denied."""
        bucket = self._get_bucket(caller_id)
        self._refill(bucket)

        if bucket.tokens >= tokens:
            bucket.tokens -= tokens
            bucket.consecutive_rejections = 0
            return RateLimitResult(
                allowed=True,
                remaining_tokens=int(bucket.tokens),
            )

        # Denied — calculate backoff
        bucket.consecutive_rejections += 1
        backoff = min(
            self._config.backoff_base * (self._config.backoff_multiplier ** (bucket.consecutive_rejections - 1)),
            self._config.backoff_max,
        )
        return RateLimitResult(
            allowed=False,
            retry_after=round(backoff, 2),
            remaining_tokens=int(bucket.tokens),
        )

    def reset(self, caller_id: Optional[str] = None):
        """Reset one or all buckets."""
        if caller_id:
            self._buckets.pop(caller_id, None)
        else:
            self._buckets.clear()

    def _get_bucket(self, caller_id: str) -> _Bucket:
        if caller_id not in self._buckets:
            self._buckets[caller_id] = _Bucket(
                tokens=float(self._config.max_tokens),
                max_tokens=self._config.max_tokens,
            )
        return self._buckets[caller_id]

    def _refill(self, bucket: _Bucket):
        now = time.time()
        elapsed = now - bucket.last_refill
        refill = elapsed * self._config.tokens_per_second
        bucket.tokens = min(bucket.tokens + refill, bucket.max_tokens)
        bucket.last_refill = now


@dataclass
class DegradeStrategy:
    """Defines how to degrade when a tool is unavailable."""
    fallback_tool: Optional[str] = None
    cached_response: Optional[Dict] = None
    human_handoff: bool = False
    message: str = ""


class DegradeManager:
    """Manages degradation strategies per tool."""

    def __init__(self):
        self._strategies: Dict[str, DegradeStrategy] = {}

    def register_strategy(self, tool_name: str, strategy: DegradeStrategy):
        self._strategies[tool_name] = strategy

    def get_strategy(self, tool_name: str) -> Optional[DegradeStrategy]:
        return self._strategies.get(tool_name)

    def should_degrade(self, tool_name: str) -> bool:
        return tool_name in self._strategies
