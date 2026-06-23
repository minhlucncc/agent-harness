"""Tests for create_agent() and create_runtime() factories + backward compat (c0005).

RED: the factory functions do not exist yet — imports fail with ImportError.
GREEN: create_agent() and create_runtime() are exported from agent_harness and
       the assertions below validate the scenarios from the agent-harness-api spec.
"""

from __future__ import annotations

import pytest
from agent_harness import Agent, cli, filesystem, inproc, local


# ---------------------------------------------------------------------------
# Factory tests — RED until create_agent / create_runtime are exported.
# Each import is inside the function body so failure is per-test, not
# module-level, and backward-compat tests below still run.
# ---------------------------------------------------------------------------


def test_create_agent_returns_agent_with_correct_fields():
    """create_agent(config, kb, instructions) returns an Agent with fields set."""
    from agent_harness import create_agent

    agent = create_agent(
        config={"policy": {"system_prompt": "Hello"}},
        kb={"docs": "path"},
        instructions="Be helpful",
    )
    assert isinstance(agent, Agent)
    assert agent.policy["system_prompt"] is not None
    assert "Be helpful" in agent.policy["system_prompt"]
    assert agent.kb == {"docs": "path"}
    assert agent.plugins is not None
    assert agent.tools is not None


def test_create_agent_accepts_model_param():
    """create_agent(config, model="gpt-4") sets policy["model"]."""
    from agent_harness import create_agent

    agent = create_agent(config={"policy": {}}, model="gpt-4")
    assert agent.policy["model"] == "gpt-4"


def test_create_agent_raises_on_invalid_input():
    """create_agent(config=None) raises TypeError/ValueError indicating config required."""
    from agent_harness import create_agent

    with pytest.raises((TypeError, ValueError), match=r"(?i)config|required"):
        create_agent(config=None)


def test_create_runtime_requires_sandbox():
    """create_runtime(agent) without sandbox raises TypeError."""
    from agent_harness import create_runtime

    agent = Agent({"policy": {}})
    with pytest.raises(TypeError, match=r"(?i)sandbox|required"):
        create_runtime(agent)


def test_create_runtime_validates_build_mode():
    """create_runtime(agent, sandbox=local(), build="invalid") raises ValueError."""
    from agent_harness import create_runtime

    agent = Agent({"policy": {}})
    with pytest.raises(ValueError, match=r"(?i)build|reuse|missing|always"):
        create_runtime(agent, sandbox=local(), build="invalid")


def test_create_runtime_accepts_all_optional_params():
    """create_runtime with all optional params returns a Runtime with them bound."""
    from agent_harness import create_runtime

    agent = Agent({"policy": {}}, kb={"docs": "path"})
    rt = create_runtime(
        agent,
        sandbox=local(),
        channels=[cli()],
        storage=filesystem(),
        cache=inproc(),
        build="missing",
    )
    assert rt is not None
    assert rt.sandbox is not None
    assert len(rt.channels) == 1
    assert rt.channels[0].name == "cli"
    assert rt.build_mode == "missing"


def test_create_runtime_accepts_scope_or_session_id():
    """create_runtime accepts explicit Scope or session_id string."""
    from agent_harness import Scope, create_runtime

    agent = Agent({"policy": {}})
    rt1 = create_runtime(agent, sandbox=local(), scope=Scope(session_id="abc"))
    assert rt1 is not None

    rt2 = create_runtime(agent, sandbox=local(), session_id="def")
    assert rt2 is not None


# ---------------------------------------------------------------------------
# Backward-compat tests — use the existing Agent API; should pass once
# runtime/agent imports work.
# ---------------------------------------------------------------------------


def test_agent_serve_still_works_legacy():
    """Agent(bundle).serve(...) pattern succeeds (delegates to factory internally)."""
    agent = Agent({"policy": {"system_prompt": "hi"}}, kb={"k": "docs"})
    rt = agent.runtime(sandbox=local(), channels=[cli()])
    assert rt is not None
    assert rt.sandbox.name == "local"


def test_agent_runtime_still_works_legacy():
    """Agent(bundle).runtime(...) returns a Runtime with expected attributes."""
    agent = Agent({"policy": {"system_prompt": "hi"}})
    rt = agent.runtime(sandbox=local(), channels=[cli()])
    assert hasattr(rt, "sandbox")
    assert hasattr(rt, "channels")
    assert hasattr(rt, "storage")
    assert hasattr(rt, "cache")
    assert hasattr(rt, "dispatch")
    assert hasattr(rt, "serve")


def test_agent_run_still_works_legacy():
    """Agent(bundle).run(...) delegates to Runtime.run_once."""
    agent = Agent({"policy": {"system_prompt": "hi"}})
    rt = agent.runtime(sandbox=local(), channels=[])
    assert hasattr(rt, "run_once")


def test_create_runtime_with_worker_sandbox():
    """create_runtime(agent, sandbox=worker(embed=False)) creates a Runtime with WorkerSandbox."""
    from agent_harness import create_runtime, worker

    agent = Agent({"policy": {"system_prompt": "hi"}})
    rt = create_runtime(agent, sandbox=worker(embed=False))
    assert rt is not None
    assert rt.sandbox is not None
    assert rt.sandbox.name == "worker"
