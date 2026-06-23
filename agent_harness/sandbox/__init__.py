"""Sandbox — the execution environment / deploy target (RFC 0024).

A Sandbox fixes the process model and supplies the default Storage + Cache. `local()` (one
long-running process, zero infra) is the first milestone; worker/docker/cfworker/remote are named
stubs for later rollout steps.
"""

from __future__ import annotations

from typing import Any

from agent_harness._stub import todo


class LocalSandbox:
    """One long-running process; direct in-process `run_turn`. Zero infra.

    `embed` controls the default KB tier: `True` = full embeddings, `False` = raw structural
    chunks (no embedding model). A no-KB agent ignores this entirely (pure LLM)."""

    name = "local"

    def __init__(self, *, embed: bool = True) -> None:
        self.embed = embed

    def default_storage(self) -> Any:
        from agent_harness.storage import filesystem

        return filesystem(embed=self.embed)

    def default_cache(self) -> Any:
        from agent_harness.cache import inproc

        return inproc()

    def client(self) -> tuple[Any, str]:
        """The SDK-callable LLM client + model from env (built once per Runtime)."""
        from agent_harness._engine import build_client

        return build_client()

    def job_settings(
        self, conversation_id: str, agent: Any, storage: Any, model: str
    ) -> tuple[Any, dict]:
        """The per-turn JobContext + settings."""
        from agent_harness._engine import build_job

        job = build_job(conversation_id)
        settings = {
            "model": model,
            "bot_id": "local",
            "skills": agent.skills,
            **storage.settings_fragment(),
        }
        return job, settings


def local(*, embed: bool = True) -> LocalSandbox:
    """Zero-infra single process — the default environment.

    `local()` = full embeddings; `local(embed=False)` = raw chunks, no embedding model (light)."""
    return LocalSandbox(embed=embed)


# Other environments — later rollout steps in RFC 0024.
worker = todo("sandbox.worker()", "rollout step 6 — production parity")
docker = todo("sandbox.docker()", "rollout step 5 — one-box self-host")
cfworker = todo("sandbox.cfworker()", "rollout step 7 — edge/serverless spike")
remote = todo("sandbox.remote()", "rollout step 7 — provider container")

__all__ = ["LocalSandbox", "local", "worker", "docker", "cfworker", "remote"]
