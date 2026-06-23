"""Storage — persistence: DB + KB/object index (RFC 0024).

`filesystem()` (KB index on disk) + `none()` (no DB; degrade via `isolated_db`) are the zero-infra
local defaults. Server backends (postgres/minio/s3/r2) are named stubs for later rollout steps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_harness._stub import todo


class FilesystemStorage:
    """No DB (isolated) + a filesystem KB index under `data_root`.

    `embed=False` builds the SQLite KG **structurally only** — raw chunks, NO embedding model
    loaded (retrieval falls back to lexical/structural). That's the lightweight tier: a usable
    local KB with minimal resources and no `sentence-transformers` download."""

    backend = "filesystem"

    def __init__(self, data_root: str | Path | None = None, *, embed: bool = True) -> None:
        self.data_root = Path(data_root) if data_root else Path(".agent-harness/local-index")
        self.embed = embed

    def settings_fragment(self) -> dict:
        return {"storage_backend": "filesystem", "data_root": str(self.data_root)}

    def kb_dir(self, kb_id: str) -> Path:
        from agent_harness._engine import LOCAL_TENANT_ID

        return self.data_root / "tenants" / LOCAL_TENANT_ID / "kbs" / kb_id

    def has_kb(self, kb_id: str) -> bool:
        """True if a local index for this KB already exists (so we can reuse, not rebuild)."""
        return self.kb_dir(kb_id).exists()

    def session_scope(self):
        from agent_harness._engine import isolated_db

        return isolated_db()

    async def build_kb(self, kb_id: str, docs_path: str) -> None:
        from agent_harness._engine import build_index

        await build_index(
            kb_id=kb_id, docs_path=docs_path, data_root=self.data_root, embed=self.embed
        )

    async def commit(self, id: str, result: Any, host: Any) -> None:
        # Local: nothing to persist (trace stays in the result object).
        return None


def filesystem(data_root: str | Path | None = None, *, embed: bool = True) -> FilesystemStorage:
    """KB index on disk, no DB — the zero-infra default. `embed=False` = raw chunks, no model."""
    return FilesystemStorage(data_root, embed=embed)


def none() -> FilesystemStorage:
    """No-DB storage (alias of filesystem() — the DB axis is `isolated_db`)."""
    return FilesystemStorage()


# Server backends — later rollout steps (5/6 in RFC 0024).
postgres = todo("storage.postgres()", "rollout step 5/6")
minio = todo("storage.minio()", "rollout step 5/6")
s3 = todo("storage.s3()", "rollout step 5/6")
r2 = todo("storage.r2()", "rollout step 7")

__all__ = ["FilesystemStorage", "filesystem", "none", "postgres", "minio", "s3", "r2"]
