"""Language-neutral specification of an exercise and its UML contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_UNIT_KINDS = frozenset({"class", "interface", "enum"})
_MEMBER_KINDS = frozenset({"field", "constructor", "method"})
_VISIBILITIES = frozenset({"public", "private", "protected", "package"})
_MODIFIERS = frozenset({"", "static", "abstract", "final"})
_RELATIONSHIP_KINDS = frozenset(
    {"inheritance", "implements", "association", "aggregation", "composition", "ambiguous"}
)


def _identifier(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.isidentifier():
        raise ValueError(f"{where} precisa ser um identificador válido: {value!r}.")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where} precisa ser texto não vazio.")
    return value


def _confidence(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} precisa ser numérico.")
    if value != value or value < 0.0 or value > 1.0:
        raise ValueError(f"{where} precisa estar entre 0.0 e 1.0: {value!r}.")
    return float(value)


def _choice(value: Any, allowed: frozenset[str], where: str) -> str:
    if value not in allowed:
        raise ValueError(
            f"{where} inválido: {value!r}. Aceitos: {', '.join(sorted(allowed))}."
        )
    return value


def _objects(values: Any, where: str):
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"Specification.from_dict: {where} precisa ser uma lista.")
    for value in values:
        if not isinstance(value, dict):
            raise ValueError(
                f"Specification.from_dict: item inválido em {where}: {value!r}."
            )
        yield value


@dataclass(frozen=True, slots=True)
class Requirement:
    text: str
    origin: str
    confidence: float
    scope: str | None = None

    def __post_init__(self) -> None:
        _text(self.text, "Requirement.text")
        _text(self.origin, "Requirement.origin")
        _confidence(self.confidence, "Requirement.confidence")
        if self.scope is not None:
            _identifier(self.scope, "Requirement.scope")


@dataclass(frozen=True, slots=True)
class Member:
    name: str
    kind: str
    type_name: str
    visibility: str
    parameters: tuple[tuple[str, str], ...] = ()
    modifiers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.name, "Member.name")
        _choice(self.kind, _MEMBER_KINDS, "Member.kind")
        _text(self.type_name, "Member.type_name")
        _choice(self.visibility, _VISIBILITIES, "Member.visibility")
        for parameter in self.parameters:
            if len(parameter) != 2:
                raise ValueError("Cada parâmetro precisa ter nome e tipo.")
            _identifier(parameter[0], "Member parameter name")
            _text(parameter[1], "Member parameter type")
        for modifier in self.modifiers:
            _choice(modifier, _MODIFIERS, "Member modifier")


@dataclass(frozen=True, slots=True)
class Unit:
    name: str
    kind: str
    members: tuple[Member, ...]
    modifiers: tuple[str, ...] = ()
    confidence: float = 1.0

    def __post_init__(self) -> None:
        _identifier(self.name, "Unit.name")
        _choice(self.kind, _UNIT_KINDS, "Unit.kind")
        for member in self.members:
            if not isinstance(member, Member):
                raise ValueError("Unit.members aceita somente Member.")
        for modifier in self.modifiers:
            _choice(modifier, _MODIFIERS, "Unit modifier")
        _confidence(self.confidence, "Unit.confidence")


@dataclass(frozen=True, slots=True)
class Relationship:
    parent: str
    child: str
    kind: str
    confidence: float
    alternatives: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _identifier(self.parent, "Relationship.parent")
        _identifier(self.child, "Relationship.child")
        _choice(self.kind, _RELATIONSHIP_KINDS, "Relationship.kind")
        _confidence(self.confidence, "Relationship.confidence")
        for alternative in self.alternatives:
            _text(alternative, "Relationship alternative")


@dataclass(frozen=True, slots=True)
class Specification:
    units: tuple[Unit, ...]
    relationships: tuple[Relationship, ...]
    requirements: tuple[Requirement, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for unit in self.units:
            if not isinstance(unit, Unit):
                raise ValueError("Specification.units aceita somente Unit.")
        for relationship in self.relationships:
            if not isinstance(relationship, Relationship):
                raise ValueError("Specification.relationships aceita somente Relationship.")
        for requirement in self.requirements:
            if not isinstance(requirement, Requirement):
                raise ValueError("Specification.requirements aceita somente Requirement.")
        for warning in self.warnings:
            _text(warning, "Specification warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "units": [
                {
                    "name": unit.name,
                    "kind": unit.kind,
                    "members": [
                        {
                            "name": member.name,
                            "kind": member.kind,
                            "type_name": member.type_name,
                            "visibility": member.visibility,
                            "parameters": [list(parameter) for parameter in member.parameters],
                            "modifiers": list(member.modifiers),
                        }
                        for member in unit.members
                    ],
                    "modifiers": list(unit.modifiers),
                    "confidence": unit.confidence,
                }
                for unit in self.units
            ],
            "relationships": [
                {
                    "parent": relationship.parent,
                    "child": relationship.child,
                    "kind": relationship.kind,
                    "confidence": relationship.confidence,
                    "alternatives": list(relationship.alternatives),
                }
                for relationship in self.relationships
            ],
            "requirements": [
                {
                    "text": requirement.text,
                    "origin": requirement.origin,
                    "confidence": requirement.confidence,
                    "scope": requirement.scope,
                }
                for requirement in self.requirements
            ],
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Specification":
        if not isinstance(data, dict):
            raise ValueError("Specification.from_dict precisa de um objeto.")
        return cls(
            units=tuple(
                Unit(
                    name=unit["name"],
                    kind=unit["kind"],
                    members=tuple(
                        Member(
                            name=member["name"],
                            kind=member["kind"],
                            type_name=member["type_name"],
                            visibility=member["visibility"],
                            parameters=tuple(
                                tuple(parameter)
                                for parameter in member.get("parameters", ())
                            ),
                            modifiers=tuple(member.get("modifiers", ())),
                        )
                        for member in _objects(unit.get("members", ()), "members")
                    ),
                    modifiers=tuple(unit.get("modifiers", ())),
                    confidence=unit.get("confidence", 1.0),
                )
                for unit in _objects(data.get("units", ()), "units")
            ),
            relationships=tuple(
                Relationship(
                    parent=relationship["parent"],
                    child=relationship["child"],
                    kind=relationship["kind"],
                    confidence=relationship["confidence"],
                    alternatives=tuple(relationship.get("alternatives", ())),
                )
                for relationship in _objects(
                    data.get("relationships", ()), "relationships"
                )
            ),
            requirements=tuple(
                Requirement(
                    text=requirement["text"],
                    origin=requirement["origin"],
                    confidence=requirement["confidence"],
                    scope=requirement.get("scope"),
                )
                for requirement in _objects(
                    data.get("requirements", ()), "requirements"
                )
            ),
            warnings=tuple(data.get("warnings", ())),
        )


def find_unit(spec: Specification, name: str) -> Unit | None:
    return next((unit for unit in spec.units if unit.name == name), None)


def members_of(unit: Unit, kind: str) -> tuple[Member, ...]:
    return tuple(member for member in unit.members if member.kind == kind)
