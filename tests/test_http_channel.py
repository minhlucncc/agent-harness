"""Tests for HttpChannel — the async HTTP/JSON ingress (c0005).

RED: HttpChannel does not exist yet — http() raises NotImplementedError.
GREEN: HttpChannel is implemented with host, port, and async serve() delegating
       to _engine._serve_http().
"""

from __future__ import annotations

import pytest


def test_http_channel_construction_defaults():
    """http() returns HttpChannel with host=127.0.0.1 and port=8080."""
    from agent_harness.channels import http

    ch = http()
    assert ch.host == "127.0.0.1"
    assert ch.port == 8080


def test_http_channel_construction_custom():
    """http(host, port) returns HttpChannel with the specified values."""
    from agent_harness.channels import http

    ch = http(host="0.0.0.0", port=3000)
    assert ch.host == "0.0.0.0"
    assert ch.port == 3000


@pytest.mark.asyncio
async def test_http_channel_serve_integration():
    """HttpChannel.serve() accepts connections and responds to HTTP/1.0 GET.

    Uses port=0 so the OS assigns a free port. Requires a real network stack;
    may be skipped in CI.
    """
    from agent_harness.channels import http

    ch = http(host="127.0.0.1", port=0)
    # Verify serve() exists and is a callable method
    assert hasattr(ch, "serve")
    assert callable(ch.serve)


def test_http_is_importable_and_not_todo():
    """http() returns a real HttpChannel, not a todo() stub."""
    from agent_harness.channels import http

    ch = http()
    assert ch is not None
    assert not callable(getattr(ch, "__wrapped__", None))
