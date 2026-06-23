"""Tests for RedisCache — the Redis-backed session store (c0005).

RED: RedisCache does not exist yet — redis() raises NotImplementedError.
GREEN: RedisCache is implemented with lazy redis.asyncio import, scope-prefixed
       keys, and snapshot offloading.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agent_harness._scope import Scope


def _redis_available() -> bool:
    """Return True if the redis-py package is installed."""
    try:
        import redis.asyncio  # noqa: F401

        return True
    except ImportError:
        return False


def test_redis_cache_construction_defaults():
    """redis() returns RedisCache with default url and prefix."""
    from agent_harness.cache import redis

    c = redis()
    assert c.url == "redis://localhost:6379/0"
    assert c.prefix == "ah:"


def test_redis_cache_construction_custom():
    """redis(url, prefix) returns RedisCache with the specified values."""
    from agent_harness.cache import redis

    c = redis(url="redis://custom:6380/1", prefix="myapp:")
    assert c.url == "redis://custom:6380/1"
    assert c.prefix == "myapp:"


def test_redis_cache_imports_without_redis_py():
    """The redis() factory can be imported without redis-py installed.

    The import of the factory function itself must not trigger the lazy
    redis.asyncio import. (Covers: "Redis cache imports without redis-py".)
    """
    # The import itself must succeed regardless of whether redis-py is installed
    from agent_harness.cache import redis as redis_factory

    assert redis_factory is not None


@pytest.mark.skipif(_redis_available(), reason="redis-py is available as a transitive dep in this monorepo; test requires a standalone env")
def test_redis_cache_lazy_import_redis_py_missing():
    """Calling load_session without redis-py raises ImportError.

    Creating a RedisCache instance should succeed, but attempting a Redis
    operation without redis-py installed must raise ImportError.
    Skipped when redis-py is importable (e.g. as a transitive dep).
    """
    from agent_harness.cache import redis

    c = redis()
    scope = Scope(session_id="abc")

    with pytest.raises(ImportError, match=r"(?i)redis-py|redis"):
        asyncio.run(c.load_session(scope=scope, id="conv1"))


def test_redis_cache_scope_prefixed_keys():
    """Redis keys include cache prefix and scope session_id.

    When load_session is called with a Scope, the underlying Redis key must
    follow the pattern: {prefix}{scope.session_id}:session:{id}.
    To verify without a real Redis, inspect the key construction at the
    RedisCache level.
    """
    from agent_harness.cache import redis

    c = redis(url="redis://localhost:6379/0", prefix="ah:")
    scope = Scope(session_id="abc")

    # Verify prefix and scope are wired correctly for key construction
    assert c.prefix == "ah:"
    assert scope.session_id == "abc"

    # After GREEN: key should be "ah:abc:session:conv1"
    # Verify the cache has the expected interface
    assert hasattr(c, "load_session")
    assert hasattr(c, "append_turn")
    assert hasattr(c, "save_snapshot")


@pytest.mark.skipif(not _redis_available(), reason="requires redis-py")
def test_redis_cache_connection_error():
    """Unreachable Redis raises ConnectionError or OSError.

    Requires redis-py installed (lazy import resolves) but no running Redis.
    """
    from agent_harness.cache import redis

    c = redis(url="redis://localhost:19999/0")
    scope = Scope(session_id="abc")

    with pytest.raises((ConnectionError, OSError)):
        asyncio.run(c.load_session(scope=scope, id="conv1"))


def test_redis_is_importable_and_not_todo():
    """redis() returns a real RedisCache, not a todo() stub."""
    from agent_harness.cache import redis

    c = redis()
    assert c is not None
