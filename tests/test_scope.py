"""Tests for the Scope isolation model (RFC 0024, c0005).

Scope is the per-runtime isolation boundary. Every cache operation, storage path,
and JobContext is scoped to this identity. Two Runtime instances with different
Scope values share nothing.
"""

from __future__ import annotations

import pytest
from agent_harness._scope import Scope


class TestScope:
    """Scope — per-runtime isolation boundary."""

    def test_generate_unique_session_ids(self):
        """Two consecutive Scope.generate() calls produce different session IDs."""
        s1 = Scope.generate()
        s2 = Scope.generate()
        assert s1.session_id != s2.session_id

    def test_resolved_tenant_id_explicit(self):
        """When tenant_id is given, resolved_tenant_id returns it verbatim."""
        s = Scope(session_id="abc", tenant_id="tenant-1")
        assert s.resolved_tenant_id == "tenant-1"

    def test_resolved_tenant_id_derived(self):
        """Without tenant_id, resolved_tenant_id derives from session_id."""
        s = Scope(session_id="abc")
        expected = "session-abc"
        assert s.resolved_tenant_id == expected
        assert s.resolved_tenant_id.startswith("session-")

    def test_frozen(self):
        """Scope is immutable after construction (frozen dataclass)."""
        s = Scope(session_id="abc")
        with pytest.raises(AttributeError):
            s.session_id = "xyz"
