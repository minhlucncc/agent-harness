"""`Runtime` — bind an agent to infra, hold channels, route, run the turn loop (RFC 0024).

The Runtime is the *harness* (an agent bound to a Sandbox + Storage + Cache), internalized. It
owns the single new glue over the engine — `dispatch` → `run_turn` — and calls it from each
channel. `agent.serve()` / `agent.runtime()` build it.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

ReplySink = Callable[[Any, Any], Awaitable[None]]


class Runtime:
    def __init__(
        self,
        agent: Any,
        *,
        sandbox: Any,
        channels: list,
        storage: Any = None,
        cache: Any = None,
        client: tuple[Any, str] | None = None,
        build: str = "reuse",
    ) -> None:
        self.agent = agent
        self.sandbox = sandbox
        self.channels = channels
        # KB build policy: "reuse" (default — never build; reuse an existing index, error if
        # missing), "missing" (build only if absent), "always" (force rebuild). Indexing is a
        # separate, explicit step (`mez index`); benching/serving must NOT silently re-embed.
        self.build_mode = build
        # A Sandbox supplies default Storage + Cache; either is overridable.
        self.storage = storage or sandbox.default_storage()
        self.cache = cache or sandbox.default_cache()
        self._kb_ready = False
        # The LLM client is built once and reused across turns (a benchmark drives many turns
        # through one Runtime). A caller may inject a prebuilt (client, model) pair.
        self._client: Any = client[0] if client else None
        self._model: str | None = client[1] if client else None

        # Per-turn policy prep (mirrors mezctl/local.run_local_turn): bind the local KB ids and
        # disable the golden head so a turn makes exactly the answer call. The agent's own policy
        # is left untouched.
        from agent_harness._engine import local_kb_id

        self._kb_ids = [local_kb_id(k) for k in agent.kb]
        policy = dict(agent.policy)
        # The harness OWNS the KB binding: allowed_kbs is exactly the locally-built KBs from the
        # `kb=` mapping. We never fall back to the policy's platform KB UUIDs — those don't exist in
        # a local sandbox (they'd send the engine to MinIO/S3). No kb -> allowed_kbs=[].
        policy["allowed_kbs"] = self._kb_ids
        gh = dict(policy.get("golden_head") or {})
        gh.update({"enabled": False, "verify": False})
        policy["golden_head"] = gh
        # A no-retrieval agent is a pure-LLM runtime: grounding/citation refusal would make it
        # refuse every turn (no KB -> no citations). So when retrieval is off, default to
        # non-grounding — unless the policy explicitly opted in. (Retrieval bots are untouched.)
        retrieval_on = "arag" in (agent.plugins or [])
        if not retrieval_on:
            policy.setdefault("require_citations", False)
            policy.setdefault("refusal_enforcement", "disabled")
        self._policy = policy

    # ── KB ───────────────────────────────────────────────────────────────────
    async def _ensure_kb(self) -> None:
        if self._kb_ready:
            return
        from agent_harness._engine import local_kb_id

        for key, docs_path in self.agent.kb.items():
            kb_id = local_kb_id(key)
            exists = self.storage.has_kb(kb_id)
            if self.build_mode == "always" or (self.build_mode == "missing" and not exists):
                await self.storage.build_kb(kb_id, docs_path)
            elif not exists:
                raise RuntimeError(
                    f"no local index for KB '{key}' at {self.storage.kb_dir(kb_id)}. "
                    f"Build it once (separate step): `mez index {key}` "
                    f"(add --no-embed for the light tier). Benching/serving reuses the index — "
                    f"it never auto-embeds."
                )
        self._kb_ready = True

    async def build_kbs(self) -> None:
        """Explicitly (re)build every KB index now. The separate indexing step."""
        from agent_harness._engine import local_kb_id

        for key, docs_path in self.agent.kb.items():
            await self.storage.build_kb(local_kb_id(key), docs_path)
        self._kb_ready = True

    def _ensure_client(self) -> tuple[Any, str]:
        if self._client is None:
            self._client, self._model = self.sandbox.client()
        return self._client, self._model

    # ── the one dispatch seam ──────────────────────────────────────────────────
    async def dispatch(self, *, id: str, input: str, reply: ReplySink) -> Any:
        """Run one turn: bind infra → `run_turn` (unchanged) → reply → persist."""
        from agent_harness._engine import require_engine

        require_engine()
        from agent_core.runtime import run_turn

        await self._ensure_kb()
        client, model = self._ensure_client()
        job, settings = self.sandbox.job_settings(id, self.agent, self.storage, model)
        session_memory = await self.cache.load_session(id)
        with self.storage.session_scope():
            result, host = await run_turn(
                self._policy,
                job,
                settings,
                input,
                client=client,
                redis=self.cache.redis,
                session_memory=session_memory,
                refusal_rules=(),
                enabled_plugins=set(self.agent.plugins),  # [] -> pure LLM, no retrieval
                save_snapshot=self.cache.save_snapshot,
            )
        await reply(result, host)
        await self.storage.commit(id, result, host)
        await self.cache.append_turn(id, result, host)
        return result

    async def run_once(self, query: str, *, conversation_id: str = "local") -> tuple[Any, Any]:
        """Channel-less single turn → (result, host). The substrate for the local loop + benches."""
        captured: dict = {}

        async def _capture(result: Any, host: Any) -> None:
            captured["v"] = (result, host)

        await self.dispatch(id=conversation_id, input=query, reply=_capture)
        return captured["v"]

    # ── serve all channels ────────────────────────────────────────────────────
    async def serve(self) -> None:
        if not self.channels:
            raise RuntimeError("no channels to serve — pass channels=[cli()] (or mezon/http/…).")
        await asyncio.gather(*(ch.serve(self) for ch in self.channels))
