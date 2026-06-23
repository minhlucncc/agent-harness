"""Cache — Redis: session cache + arq queue + pub/sub (RFC 0024).

`inproc()` runs with no Redis: `redis=None` and (for now) a stateless session. Multi-turn memory
without Redis (an in-process SessionMemoryStore) is the next increment; `redis()` is the server
backend stub.
"""

from __future__ import annotations

from typing import Any


class InprocCache:
    """No Redis. `run_turn` degrades its session/golden paths through their own try/except."""

    redis = None
    # `run_turn`'s stateless save seam; None = don't offload a snapshot.
    save_snapshot = None

    async def load_session(self, id: str) -> Any:
        # First milestone: stateless turns. In-process multi-turn memory lands next.
        return None

    async def append_turn(self, id: str, result: Any, host: Any) -> None:
        return None


def inproc() -> InprocCache:
    """No Redis — asyncio/in-process; the zero-infra default."""
    return InprocCache()


# Server cache — later rollout step (5/6 in RFC 0024).


class RedisCache:
    """Redis-backed session cache with lazy import and scope-prefixed keys.

    The ``redis.asyncio`` import is deferred until the first Redis operation,
    so the factory function can be imported without ``redis-py`` installed.
    """

    redis = None  # Overwritten when a real Redis client resolves

    def __init__(self, url: str = "redis://localhost:6379/0", prefix: str = "ah:") -> None:
        self.url = url
        self.prefix = prefix
        self._client: Any = None

    def _ensure_client(self) -> Any:
        """Lazily import ``redis.asyncio`` and create the client on first use."""
        if self._client is None:
            try:
                import redis.asyncio  # type: ignore[import-untyped]
            except ImportError:
                raise ImportError(
                    "redis-py is required for RedisCache: pip install agent-harness[redis]"
                )
            self._client = redis.asyncio.from_url(self.url)
        return self._client

    async def load_session(self, scope: Any, id: str) -> Any:
        """Load a session from Redis using a scope-prefixed key.

        Raises ``ImportError`` when ``redis-py`` is not installed.
        Raises ``ConnectionError`` or ``OSError`` when Redis is unreachable.
        """
        client = self._ensure_client()
        key = f"{self.prefix}{scope.session_id}:session:{id}"
        try:
            return await client.get(key)
        except OSError:
            raise
        except Exception as exc:
            # redis-py wraps OSErrors in redis.exceptions.ConnectionError which
            # inherits from Exception, not builtin ConnectionError. Convert it
            # so the public API raises built-in exceptions.
            if hasattr(exc, "__module__") and "redis" in (exc.__module__ or ""):
                raise ConnectionError(str(exc)) from exc
            raise

    async def append_turn(self, scope: Any, id: str, result: Any, host: Any) -> None:
        """Append a turn to Redis using a scope-prefixed key."""
        client = self._ensure_client()
        # Scope-prefixed key pattern; body serialisation lands in a later increment.
        _key = f"{self.prefix}{scope.session_id}:turn:{id}"
        _ = client

    async def save_snapshot(self, state: Any) -> None:
        """Offload a snapshot using a scope-prefixed key."""
        if self._client is not None:
            pass  # Snapshot offloading lands in a later increment.


def redis(*, url: str = "redis://localhost:6379/0", prefix: str = "ah:") -> RedisCache:
    """A Redis-backed session cache — production default for multi-turn memory."""
    return RedisCache(url=url, prefix=prefix)


__all__ = ["InprocCache", "inproc", "RedisCache", "redis"]
