"""Adapter registry. Imports are lazy so the Java adapter can import this package."""

from __future__ import annotations

from collections.abc import Callable

from .base import (
    CompileResult,
    LanguageAdapter,
    Rule,
    RunResult,
    SourceMatchers,
    Toolchain,
)

Factory = Callable[[], LanguageAdapter]


def _factories(*, allow_stub: bool) -> dict[str, Factory]:
    from .java8 import Java8Adapter

    factories: dict[str, Factory] = {"java8": Java8Adapter}
    if allow_stub:
        from .stub import StubAdapter

        factories["stub"] = StubAdapter
    return factories


def adapter_ids(*, allow_stub: bool = False) -> tuple[str, ...]:
    return tuple(sorted(_factories(allow_stub=allow_stub)))


def resolve_adapter(adapter_id: str, *, allow_stub: bool = False) -> LanguageAdapter:
    factories = _factories(allow_stub=allow_stub)
    factory = factories.get(adapter_id)
    if factory is None:
        raise ValueError(
            f"Adaptador desconhecido: {adapter_id}. "
            f"Disponíveis: {', '.join(sorted(factories)) or '(nenhum)'}."
        )
    return factory()


__all__ = [
    "CompileResult",
    "LanguageAdapter",
    "Rule",
    "RunResult",
    "SourceMatchers",
    "Toolchain",
    "adapter_ids",
    "resolve_adapter",
]
