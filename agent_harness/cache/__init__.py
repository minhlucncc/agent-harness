"""Cache — Redis: session cache + arq queue + pub/sub (RFC 0024).

`inproc()` runs with no Redis: `redis=None` and (for now) a stateless session. Multi-turn memory
without Redis (an in-process SessionMemoryStore) is the next increment; `redis()` is the server
backend stub.
"""

from __future__ import annotations

from typing import Any

from agent_harness._stub import todo


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
redis = todo("cache.redis()", "rollout step 5/6")

__all__ = ["InprocCache", "inproc", "redis"]
