"""agent_harness — run any Mezon bot on any environment (RFC 0024).

The cleanest surface is one object and one method::

    from agent_harness import Agent, local, mezon, cli

    agent = Agent("bots/funix/config.json", kb={"funix-docs": "docs/funix/documents"})
    agent.serve(sandbox=local(), channels=[mezon(), cli()])

    # zero-infra default (local() + cli()):
    Agent("bots/funix/config.json").serve()

`Agent(...)` is the bot *definition* (a BotPolicy + ADK building blocks, no infra). `.serve()`
builds the Runtime that binds it to a Sandbox (which supplies Storage + Cache) and serves the
Channels. The turn engine (`run_turn`) is never modified — the harness only feeds it.
"""

from __future__ import annotations

from agent_harness._scope import Scope
from agent_harness.agent import Agent, create_agent
from agent_harness.cache import inproc, redis
from agent_harness.channels import cli, cron, http, mezon, queue
from agent_harness.runtime import Runtime, create_runtime
from agent_harness.sandbox import cfworker, docker, local, remote, worker
from agent_harness.storage import filesystem, minio, none, postgres, r2, s3

__all__ = [
    "Agent",
    # factory API + isolation (c0005)
    "Scope",
    "create_agent",
    "create_runtime",
    "Runtime",
    # sandboxes (the environment knob)
    "local",
    "worker",
    "docker",
    "cfworker",
    "remote",
    # channels (ingress)
    "cli",
    "http",
    "mezon",
    "queue",
    "cron",
    # storage / cache (overrides; a sandbox supplies defaults)
    "filesystem",
    "none",
    "postgres",
    "minio",
    "s3",
    "r2",
    "inproc",
    "redis",
]
