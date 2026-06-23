"""Channel — ingress: verify → parse → dispatch → reply (RFC 0024).

`cli()` (a stdin REPL) is the first milestone — it proves the harness end-to-end with no provider
protocol. http/mezon/queue/cron are named stubs for later rollout steps.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agent_harness._stub import todo


class CliChannel:
    """A terminal REPL: read a line, run a turn, print the answer."""

    name = "cli"

    def __init__(self, *, prompt: str = "you> ", conversation_id: str = "local-cli") -> None:
        self.prompt = prompt
        self.conversation_id = conversation_id

    def conversation_key(self, event: Any = None) -> str:
        return self.conversation_id

    async def serve(self, runtime: Any) -> None:
        print("agent-harness CLI — type a message, /exit to quit.")
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, input, self.prompt)
            except (EOFError, KeyboardInterrupt):
                print()
                return
            line = line.strip()
            if not line:
                continue
            if line in {"/exit", "/quit", "/q"}:
                return
            await runtime.dispatch(id=self.conversation_key(), input=line, reply=self._reply)

    async def _reply(self, result: Any, host: Any) -> None:
        status = getattr(result, "status", None)
        text = getattr(result, "text", "") or ""
        tag = f"[{status}] " if status and status != "answered" else ""
        print(f"bot> {tag}{text}")
        cites = getattr(result, "citations", None) or []
        if cites:
            refs = [getattr(c, "source_ref", None) or getattr(c, "ref", str(c)) for c in cites]
            print("     citations: " + ", ".join(str(r) for r in refs))


def cli(*, prompt: str = "you> ") -> CliChannel:
    """A stdin REPL channel — the first ingress milestone."""
    return CliChannel(prompt=prompt)


# Other ingress — later rollout steps in RFC 0024.
http = todo("channels.http()", "rollout step 5 — HTTP/SSE ingress")
mezon = todo("channels.mezon()", "rollout step 4 — Python Mezon WS channel")
queue = todo("channels.queue()", "rollout step 6 — arq consumer (prod)")
cron = todo("channels.cron()", "rollout step — scheduler tick")

__all__ = ["CliChannel", "cli", "http", "mezon", "queue", "cron"]
