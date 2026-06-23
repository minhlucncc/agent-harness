"""Package-level tests for agent-harness: imports, metadata, and surface (RFC 0024).

These are the RED tests — they MUST fail on the current code and drive the rename/
publish-readiness implementation (Green) in the accompanying tasks.

"""  # noqa: D205

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────


def _package_root() -> Path:
    """Return the absolute path to ``packages/agent-harness/``.

    Uses ``agent_harness.__file__`` to locate the package directory so the path is
    always correct regardless of where from tests are run.
    """
    import agent_harness  # noqa: F811

    # __file__ is e.g. /.../packages/agent-harness/agent_harness/__init__.py
    return Path(agent_harness.__file__).resolve().parent.parent


# ── 1. import surface ───────────────────────────────────────────────────────


def test_import_agent_harness() -> None:
    """``import agent_harness`` exposes ``Agent`` + all factory names."""
    import agent_harness as h

    # The core object
    assert hasattr(h, "Agent"), "Agent not exposed"
    # Sandboxes
    for name in ("local", "worker", "docker", "cfworker", "remote"):
        assert hasattr(h, name), f"{name} not exposed"
    # Channels
    for name in ("cli", "http", "mezon", "queue", "cron"):
        assert hasattr(h, name), f"{name} not exposed"
    # Storage
    for name in ("filesystem", "none", "postgres", "minio", "s3", "r2"):
        assert hasattr(h, name), f"{name} not exposed"
    # Cache
    for name in ("inproc", "redis"):
        assert hasattr(h, name), f"{name} not exposed"

    # Factory API + Scope (c0005)
    for name in ("Scope", "create_agent", "create_runtime", "Runtime"):
        assert hasattr(h, name), f"{name} not exposed"


def test_no_dangling_legacy_import_path() -> None:
    """No source file under packages/agent-harness references the legacy name.

    Runs ``grep`` in a subprocess and asserts zero matches.
    """
    root = _package_root()
    result = subprocess.run(
        ["grep", "-rnI", "--exclude=test_package.py", r"mezon_harness\|mezon-harness", str(root)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    # grep exits 0 when it finds matches, 1 when it finds none.
    assert result.returncode != 0, (
        f"Found {result.stdout.count(chr(10))} legacy references in packages/agent-harness:\n"
        f"{result.stdout[:2000]}"
    )


# ── 2. engine-missing error ─────────────────────────────────────────────────


def test_engine_missing_mentions_engine_extra() -> None:
    """``EngineMissing()`` error message contains ``[engine]``.

    Inside the monorepo the engine deps ARE available so ``require_engine()``
    may not raise (it is tested separately). The fallback asserts the template
    that ``_engine.py`` constructs.
    """
    from agent_harness._engine import EngineMissing, require_engine

    # 1) Direct construction
    msg = str(EngineMissing("test"))
    assert "[engine]" in msg, f"EngineMissing message did not mention [engine]; got: {msg!r}"

    # 2) The require_engine function — inside the monorepo the engine deps ARE
    #    available, so it likely won't raise. As a fallback, verify the
    #    *template* contains [engine] by inspecting the source.
    #    We also try calling it and accept either a raise (engine missing) or
    #    success (engine present) — the assertion is on the error template.
    try:
        require_engine()
    except EngineMissing as exc:
        assert "[engine]" in str(exc), (
            f"require_engine() raised EngineMissing without [engine]; got: {str(exc)!r}"
        )

    # Fallback: inspect the error-message string in _engine.py source
    from agent_harness import _engine as agent_harness_engine_mod

    eng_path = Path(agent_harness_engine_mod.__file__)
    src = eng_path.read_text(encoding="utf-8")
    # Find the pip-install hint line
    for line in src.splitlines():
        if "[engine]" in line:
            break
    else:
        raise AssertionError("No line in _engine.py contains '[engine]' in the raise/call path")


# ── 3. thin import — no engine packages loaded ──────────────────────────────


def test_thin_import_constructs_agent_without_engine() -> None:
    """Constructing an ``Agent`` does not import engine packages.

    After ``import agent_harness; Agent(...)``, none of ``agent_core``,
    ``rag_core``, ``arag_core``, or ``worker_ingest`` should be in
    ``sys.modules``. Additionally, importing ``http`` (stdlib-backed) and
    ``redis`` (lazy-import) must not trigger engine loading.
    """
    # Clear any pre-loaded engine modules that might have leaked from other tests
    for mod in ("agent_core", "rag_core", "arag_core", "worker_ingest"):
        sys.modules.pop(mod, None)

    import agent_harness as h

    agent = h.Agent({"policy": {"system_prompt": "hi"}})
    assert agent is not None

    for mod in ("agent_core", "rag_core", "arag_core", "worker_ingest"):
        assert mod not in sys.modules, (
            f"engine module {mod} is loaded after thin Agent construction"
        )

    # HTTP channel uses stdlib only — must not trigger engine loading
    from agent_harness.channels import http

    ch = http()
    assert ch is not None
    for mod in ("agent_core", "rag_core", "arag_core", "worker_ingest"):
        assert mod not in sys.modules, (
            f"engine module {mod} is loaded after http() import"
        )

    # Redis cache uses lazy import — importing the factory must not trigger engine loading
    from agent_harness.cache import redis

    c = redis()
    assert c is not None
    for mod in ("agent_core", "rag_core", "arag_core", "worker_ingest"):
        assert mod not in sys.modules, (
            f"engine module {mod} is loaded after redis() import"
        )


# ── 4. build metadata — wheel inspection ────────────────────────────────────


def test_wheel_contains_metadata() -> None:
    """``uv build`` in packages/agent-harness produces a wheel + sdist with MIT license, README, URLs, classifiers."""
    root = _package_root()
    with tempfile.TemporaryDirectory(prefix="ah-build-") as tmp:
        tmpdir = Path(tmp)
        result = subprocess.run(
            ["uv", "build", "--out-dir", str(tmpdir)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, f"uv build failed (rc={result.returncode}):\n{result.stderr}"

        # Exactly one wheel and one sdist for agent_harness
        wheels = sorted(tmpdir.glob("agent_harness-*.whl"))
        sdists = sorted(tmpdir.glob("agent_harness-*.tar.gz"))
        # Allow other dists (there should be exactly 1 of each)
        assert len(wheels) >= 1, f"No wheel found in {tmpdir} -- files: {list(tmpdir.iterdir())}"
        assert len(sdists) >= 1, f"No sdist found in {tmpdir}"

        wheel = wheels[0]

        # Inspect wheel metadata
        with zipfile.ZipFile(str(wheel), "r") as zf:
            names = zf.namelist()

            # Find the METADATA file (may be in a distinfo dir like agent_harness-0.1.0.dist-info/METADATA)
            meta_candidates = [n for n in names if n.endswith(".dist-info/METADATA")]
            assert meta_candidates, f"No METADATA found in wheel; entries:\n{names}"
            meta = zf.read(meta_candidates[0]).decode("utf-8")

            # License
            assert re.search(r"^License:\s*MIT", meta, re.MULTILINE), (
                f"METADATA missing 'License: MIT':\n{meta[:2000]}"
            )
            # Name
            assert re.search(r"^Name:\s*agent-harness", meta, re.MULTILINE), (
                f"METADATA missing 'Name: agent-harness':\n{meta[:2000]}"
            )
            # Classifiers
            assert "License :: OSI Approved :: MIT License" in meta, (
                f"METADATA missing MIT classifier:\n{meta[:2000]}"
            )
            # Project URLs
            assert "Project-URL" in meta, f"METADATA missing Project-URL:\n{meta[:2000]}"
            # README (long description) — it's the body after the headers
            assert "RFC 0024" in meta or "agent-harness" in meta, (
                f"METADATA body seems empty/unrelated:\n{meta[:2000]}"
            )


def test_wheel_contains_py_typed() -> None:
    """The built wheel contains ``agent_harness/py.typed``."""
    root = _package_root()
    with tempfile.TemporaryDirectory(prefix="ah-build-") as tmp:
        tmpdir = Path(tmp)
        subprocess.run(
            ["uv", "build", "--out-dir", str(tmpdir)],
            cwd=str(root),
            capture_output=True,
            timeout=120,
            check=True,
        )
        wheels = sorted(tmpdir.glob("agent_harness-*.whl"))
        assert len(wheels) >= 1, "No wheel built"
        with zipfile.ZipFile(str(wheels[0]), "r") as zf:
            names = zf.namelist()
        py_typed_entries = [n for n in names if "py.typed" in n]
        assert py_typed_entries, f"No py.typed entry in wheel; entries:\n{names}"


# ── 5. README and LICENSE exist ─────────────────────────────────────────────


def test_readme_and_license_exist() -> None:
    """``LICENSE`` and ``README.md`` exist at the package root with correct content."""
    root = _package_root()

    readme = root / "README.md"
    license_file = root / "LICENSE"

    assert readme.exists(), f"README.md not found at {readme}"
    assert license_file.exists(), f"LICENSE not found at {license_file}"

    license_text = license_file.read_text(encoding="utf-8")
    assert "MIT" in license_text, "LICENSE does not mention MIT"
    assert "minhlucncc" in license_text, "LICENSE does not contain copyright holder 'minhlucncc'"

    readme_text = readme.read_text(encoding="utf-8")
    assert "RFC 0024" in readme_text or "agent-harness" in readme_text, (
        "README.md appears empty or unrelated"
    )
