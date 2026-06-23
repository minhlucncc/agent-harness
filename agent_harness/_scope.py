"""Scope — per-runtime isolation boundary (RFC 0024)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class Scope:
    """Uniquely identifies a runtime execution context for isolation.

    Every cache operation, storage path, and JobContext is scoped to this identity.
    Two Runtime instances with different Scope values share nothing.

    Provide an explicit ``session_id`` to resume a prior session, or use
    ``Scope.generate()`` to create a fresh, unique scope.
    """

    session_id: str
    tenant_id: str | None = None

    @classmethod
    def generate(cls, *, tenant_id: str | None = None) -> Scope:
        """Create a new unique scope with an auto-generated session_id."""
        return cls(session_id=uuid4().hex, tenant_id=tenant_id)

    @property
    def resolved_tenant_id(self) -> str:
        """The effective tenant: explicit or derived deterministically from session."""
        return self.tenant_id or f"session-{self.session_id[:8]}"
