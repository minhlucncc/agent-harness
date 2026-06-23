"""`Agent` — the bot definition (RFC 0024).

Pure declaration, no infra: a base `BotPolicy` + ADK building blocks (tools / skills / plugins /
instructions / kb) + arbitrary field overrides. `.serve()` / `.runtime()` bind it to a Sandbox and
run it; the engine (`run_turn`) is fed, never modified.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_policy(config: str | dict | Path) -> dict:
    """Resolve the base `BotPolicy` from a bundle path / dict.

    A bot bundle (e.g. `bots/funix/config.json`) nests the policy under ``"policy"``; a bare
    policy dict is used as-is. Returns a fresh dict so overrides never mutate the caller's."""
    if isinstance(config, dict):
        bundle = config
    else:
        bundle = json.loads(Path(config).read_text(encoding="utf-8"))
    policy = bundle.get("policy", bundle) if isinstance(bundle, dict) else {}
    return dict(policy)


class Agent:
    """A bot definition. Construct with the policy + building blocks; `.serve()` to run.

    agent = Agent("bots/funix/config.json", kb={"funix-docs": "docs/funix/documents"})
    agent.serve(sandbox=local(), channels=[mezon(), cli()])
    """

    def __init__(
        self,
        config: str | dict | Path,
        *,
        kb: dict[str, str] | None = None,
        tools: Any = (),
        skills: Any = (),
        plugins: Any = None,
        instructions: str | None = None,
        **overrides: Any,
    ) -> None:
        self.policy = _load_policy(config)
        self.kb = dict(kb or {})
        self.tools = list(tools)
        self.skills = list(skills)
        # Plugins: explicit list wins; otherwise default to retrieval IFF there's a KB. A no-KB
        # agent is therefore a pure-LLM runtime out of the box (no retrieval, minimal resources).
        # Force no retrieval with `plugins=[]`, or force it on with `plugins=["arag"]`.
        if plugins is not None:
            self.plugins = list(plugins)
        else:
            self.plugins = ["arag"] if self.kb else []
        if instructions:
            base = (self.policy.get("system_prompt") or "").rstrip()
            self.policy["system_prompt"] = (base + "\n\n" + instructions).strip()
        for key, value in overrides.items():
            self.policy[key] = value

    # ── run ──────────────────────────────────────────────────────────────────
    def runtime(
        self,
        *,
        sandbox: Any = None,
        channels: Any = None,
        storage: Any = None,
        cache: Any = None,
        build: str = "reuse",
    ) -> Any:
        """Build (but don't start) the Runtime that binds this agent to infra + channels.

        `build` defaults to "reuse" — the KB index is never auto-built; indexing is a separate
        step (`mez index`). Use "missing" to build once if absent, "always" to force a rebuild."""
        from agent_harness.channels import cli
        from agent_harness.runtime import Runtime
        from agent_harness.sandbox import local

        return Runtime(
            self,
            sandbox=sandbox or local(),
            channels=list(channels) if channels else [cli()],
            storage=storage,
            cache=cache,
            build=build,
        )

    def serve(
        self,
        *,
        sandbox: Any = None,
        channels: Any = None,
        storage: Any = None,
        cache: Any = None,
        build: str = "reuse",
    ) -> None:
        """Build the Runtime and serve it (blocking). Defaults: zero-infra local() + cli()."""
        import asyncio

        rt = self.runtime(
            sandbox=sandbox, channels=channels, storage=storage, cache=cache, build=build
        )
        asyncio.run(rt.serve())

    async def run(
        self,
        query: str,
        *,
        sandbox: Any = None,
        storage: Any = None,
        cache: Any = None,
        client: Any = None,
        build: str = "reuse",
        conversation_id: str = "local",
    ) -> tuple[Any, Any]:
        """Run ONE turn (no channel) → (result, host). The local loop + benchmarks build on this.

        Reuse one Agent across many `run(...)` calls (e.g. a benchmark) by holding the Runtime via
        `agent.runtime(...)` and calling `.run_once(...)` — the KB + client are then built once.
        `build` defaults to "reuse": the index is never auto-built (indexing is `mez index`)."""
        from agent_harness.runtime import Runtime
        from agent_harness.sandbox import local

        rt = Runtime(
            self,
            sandbox=sandbox or local(),
            channels=[],
            storage=storage,
            cache=cache,
            client=client,
            build=build,
        )
        return await rt.run_once(query, conversation_id=conversation_id)
