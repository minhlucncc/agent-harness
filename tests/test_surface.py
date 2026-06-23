"""The thin harness surface must work without the engine installed (RFC 0024)."""

from __future__ import annotations

import pytest

from agent_harness import Agent, cli, filesystem, inproc, local


def test_agent_definition_from_dict():
    a = Agent(
        {"policy": {"system_prompt": "hi", "allowed_kbs": []}},
        kb={"k": "docs"},
        instructions="Be terse.",
        skills=["s1"],
        model="MiniMax-M2.7",
    )
    assert a.kb == {"k": "docs"}
    assert a.plugins == ["arag"]  # default retrieval plugin
    assert a.skills == ["s1"]
    assert a.policy["system_prompt"].endswith("Be terse.")
    assert a.policy["model"] == "MiniMax-M2.7"  # **overrides land on the policy


def test_runtime_build_local_defaults():
    a = Agent({"policy": {"system_prompt": "hi"}}, kb={"funix-docs": "docs/funix"})
    rt = a.runtime(sandbox=local(), channels=[cli()])
    assert rt.storage.backend == "filesystem"
    assert type(rt.cache).__name__ == "InprocCache"
    assert rt._kb_ids == ["local-funix-docs"]
    assert [c.name for c in rt.channels] == ["cli"]
    # golden head disabled + KB bound on the per-turn policy, agent policy untouched
    assert rt._policy["golden_head"] == {"enabled": False, "verify": False}
    assert rt._policy["allowed_kbs"] == ["local-funix-docs"]
    assert "golden_head" not in a.policy


def test_zero_infra_defaults():
    assert filesystem().backend == "filesystem"
    assert inproc().redis is None


def test_no_kb_agent_is_pure_llm():
    # No KB -> no retrieval plugin by default (lightest runtime, no index build).
    a = Agent({"policy": {"system_prompt": "hi"}})
    assert a.plugins == []
    assert a.kb == {}


def test_plugins_explicit_override():
    assert Agent({"policy": {}}, plugins=["arag", "memory"]).plugins == ["arag", "memory"]
    assert Agent({"policy": {}}, kb={"k": "d"}, plugins=[]).plugins == []  # force off even with KB


def test_lightweight_embed_tier():
    from agent_harness import local

    assert filesystem(embed=False).embed is False
    assert local(embed=False).default_storage().embed is False
    assert local().default_storage().embed is True


@pytest.mark.parametrize(
    "factory", ["worker", "docker", "cfworker", "remote", "http", "mezon", "queue"]
)
def test_unbuilt_providers_fail_loudly(factory):
    import agent_harness as h

    with pytest.raises(NotImplementedError, match="RFC 0024"):
        getattr(h, factory)()


def test_reuse_is_default_no_autobuild():
    # Default build mode is "reuse": the index is never auto-built (separate `mez index` step).
    a = Agent({"policy": {}}, kb={"funix-docs": "docs"})
    rt = a.runtime(sandbox=local(), channels=[cli()])
    assert rt.build_mode == "reuse"
    assert a.runtime(build="always").build_mode == "always"
    assert a.runtime(build="missing").build_mode == "missing"


async def test_reuse_errors_when_index_missing(tmp_path):
    # reuse + a missing index -> a helpful error pointing at `mez index`, NOT a silent rebuild.
    from agent_harness.storage import filesystem

    a = Agent({"policy": {}}, kb={"funix-docs": "docs"})
    rt = a.runtime(sandbox=local(), storage=filesystem(tmp_path), build="reuse")
    with pytest.raises(RuntimeError, match="mez index"):
        await rt._ensure_kb()


def test_storage_has_kb(tmp_path):
    from agent_harness._engine import LOCAL_TENANT_ID
    from agent_harness.storage import filesystem

    st = filesystem(tmp_path)
    assert st.has_kb("local-x") is False
    (tmp_path / "tenants" / LOCAL_TENANT_ID / "kbs" / "local-x").mkdir(parents=True)
    assert st.has_kb("local-x") is True
