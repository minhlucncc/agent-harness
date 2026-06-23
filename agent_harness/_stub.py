"""Stub factories for the providers defined in RFC 0024 but not yet implemented.

The first milestone ships the zero-infra path (`local()` + `filesystem()`/`none()` + `inproc()` +
`cli()`). The other providers are real, named seams in the design — calling one before it's built
fails loudly with a pointer, rather than silently behaving like local.
"""

from __future__ import annotations

from typing import Any, Callable


def todo(name: str, step: str) -> Callable[..., Any]:
    def factory(*_args: Any, **_kwargs: Any) -> Any:
        raise NotImplementedError(
            f"{name} is specified in RFC 0024 but not implemented yet ({step}). "
            "The zero-infra path local()+filesystem()+inproc()+cli() is the first milestone."
        )

    return factory
