"""Small immutable model for a Java-oriented UML contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JavaMember:
    name: str
    type_name: str
    visibility: str
    parameters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class JavaClass:
    name: str
    fields: tuple[JavaMember, ...]
    methods: tuple[JavaMember, ...]


@dataclass(frozen=True)
class Relationship:
    parent: str
    child: str
    kind: str
    confidence: float
    alternatives: tuple[str, ...] = ()


@dataclass(frozen=True)
class JavaContract:
    classes: tuple[JavaClass, ...]
    relationships: tuple[Relationship, ...]
    warnings: tuple[str, ...] = ()
