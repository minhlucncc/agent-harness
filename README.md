# agent-harness

Run any bot on any environment — the thin surface of the [Mezon](https://github.com/minhlucncc/platform) bot-harness runtime (RFC 0024).

One object, one method:

```python
from agent_harness import Agent, local, cli

agent = Agent("bots/funix/config.json", kb={"funix-docs": "docs/funix/documents"})
agent.serve(sandbox=local(), channels=[cli()])
```

`Agent(...)` is the bot _definition_ (a BotPolicy + building blocks, no infra). `.serve()` builds the
Runtime that binds it to a Sandbox (which supplies Storage + Cache) and serves the Channels.

## Install

**Thin surface** (stdlib-only — no engine deps):

```bash
pip install agent-harness
```

**With the in-process engine** (requires the full monorepo workspace — the engine packages are not
on PyPI):

```bash
pip install 'agent-harness[engine]'
```

The `[engine]` extra pulls `agent-core`, `rag-core`, `arag-core`, and `worker-ingest`, which are
workspace-only packages. Outside the monorepo, import and construct `Agent` without engine deps;
invoking an engine-backed path raises `EngineMissing` with a hint about the `[engine]` extra.

## Quickstart

```python
from agent_harness import Agent, local, cli

# Pure-LLM agent (no KB, no retrieval)
agent = Agent({"policy": {"system_prompt": "You are a helpful assistant."}})
agent.serve(sandbox=local(), channels=[cli()])
```

See [RFC 0024](docs/design/0024-bot-harness.md) for the full design rationale.
