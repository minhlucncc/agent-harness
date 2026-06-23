"""The proven in-process engine seams (RFC 0024).

These wrap the existing engine without touching it — the same seams `mezctl chat --local`
(`apps/cli/mezctl/local.py`) already uses: a no-DB context, the real LLM client from
`rag_core` config, the local filesystem KB build, and the `JobContext` for a local turn. They
are imported lazily so the thin `agent_harness` surface stays installable without the engine.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Any

# A fixed local-dev tenant id; the local index ACL is written for this principal (matches
# mezctl's local loop so a KB built by either path is readable by the other).
LOCAL_TENANT_ID = "00000000-0000-0000-0000-0000000010ca"


class EngineMissing(RuntimeError):
    """Raised when the engine packages for the in-process path aren't installed."""

    def __init__(self, message: str = ""):
        hint = "  Install with `pip install 'agent-harness[engine]'`"
        super().__init__(message + hint if message else hint.strip())


def require_engine() -> None:
    """Fail with an actionable message if the `[engine]` extra isn't installed."""
    missing = []
    for mod in ("agent_core", "rag_core", "arag_core", "worker_ingest"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        raise EngineMissing(
            "the in-process harness needs the engine packages "
            f"({', '.join(missing)}). Install them with `pip install 'agent-harness[engine]'` "
            "(or run inside a workspace that vendors the platform)."
        )


def local_kb_id(key: str) -> str:
    return "local-" + key


@contextlib.contextmanager
def isolated_db():
    """No-DB context: `rag_core.db.get_session` becomes an empty async generator so the
    refusal-rules / golden / memo paths degrade through their own try/except. Mirrors the
    proven benchmark/`mezctl --local` seam."""
    import rag_core.db as _db

    try:
        import agent_core.golden_cache as _gc  # pyright: ignore[reportMissingImports]
    except ImportError:  # pragma: no cover
        _gc = None

    async def _empty_session():
        if False:  # an async generator that yields nothing
            yield

    saved_db = _db.get_session
    saved_gc = getattr(_gc, "get_session", None) if _gc is not None else None
    _db._engine = None
    _db.get_session = _empty_session
    if _gc is not None and saved_gc is not None:
        _gc.get_session = _empty_session
    try:
        yield
    finally:
        _db.get_session = saved_db
        if _gc is not None and saved_gc is not None:
            _gc.get_session = saved_gc
        _db._engine = None


def build_client() -> tuple[Any, str]:
    """Build the real SDK-callable LLM client + model from `rag_core` config."""
    from agent_core.clients.client import mezon_client
    from rag_core.llm.provider import _global_fallback

    provider = _global_fallback()
    if not provider.api_key or not provider.base_url:
        raise EngineMissing(
            "LLM provider not configured — set ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN "
            "and ANTHROPIC_MODEL in your environment/.env."
        )
    return mezon_client(provider), provider.model


async def build_index(
    *,
    kb_id: str,
    docs_path: str | Path,
    data_root: str | Path,
    embed: bool = True,
    tenant_id: str | None = None,
) -> Path:
    """Build/refresh the local filesystem KB index from a docs folder."""
    from worker_ingest.flows.local_docs import build_local_index

    return await build_local_index(
        kb_id=kb_id,
        tenant_id=tenant_id or LOCAL_TENANT_ID,
        docs_path=docs_path,
        data_root=data_root,
        embed=embed,
    )


def build_job(
    conversation_id: str,
    *,
    user_id: str = "local-user",
    channel_id: str = "",
    clan_id: str | None = None,
    scope: Any = None,
) -> Any:
    """A local-turn `JobContext` (the identity bag a turn runs under).

    When ``scope`` is provided, ``scope.resolved_tenant_id`` is used as the
    tenant identifier instead of the hardcoded ``LOCAL_TENANT_ID``.
    """
    import uuid

    from agent_core.models.job import JobContext

    tenant_id = scope.resolved_tenant_id if scope else LOCAL_TENANT_ID

    return JobContext(
        tenant_id=tenant_id,
        workspace_id="",
        user_id=user_id,
        group_ids=[],
        conversation_id=str(conversation_id or uuid.uuid4()),
        bot_version_id="",
        principals={},
        channel_id=channel_id,
        deployment_id="local",
        clan_id=clan_id,
    )


async def _serve_http(host: str, port: int, runtime: Any) -> None:
    """Minimal HTTP/1.0 server using stdlib ``asyncio.start_server``.

    Parses ``GET /<query> HTTP/1.0``, calls ``runtime.dispatch()`` with the query
    path, and writes back an ``HTTP/1.0 200 OK`` response with a JSON body.
    Cancels gracefully on ``asyncio.CancelledError``.
    """

    async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode("utf-8").strip()
            if not request_line:
                writer.close()
                return
            parts = request_line.split()
            if len(parts) < 2:
                writer.write(b"HTTP/1.0 400 Bad Request\r\n\r\n")
                await writer.drain()
                writer.close()
                return
            path = parts[1].lstrip("/")

            # Read headers until empty line
            while True:
                line = await reader.readline()
                if line in (b"\r\n", b"\n", b""):
                    break

            async def _noop(_result: Any, _host: Any) -> None:
                pass

            result = await runtime.dispatch(id=path, input=path, reply=_noop)
            text = getattr(result, "text", "") or ""
            body = json.dumps({"text": text}).encode("utf-8")
            writer.write(
                b"HTTP/1.0 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                b"\r\n" + body
            )
            await writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception:
            try:
                writer.write(b"HTTP/1.0 500 Internal Server Error\r\n\r\n")
                await writer.drain()
            except Exception:
                pass
        finally:
            writer.close()

    server = await asyncio.start_server(_handle, host=host, port=port)
    async with server:
        await server.serve_forever()
