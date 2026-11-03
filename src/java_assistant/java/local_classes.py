"""Adopt the API of compiled classes already present in the project folder.

Some exercise folders ship compiled classes (reference classes or a local
validator) whose public API is stricter than the statement text: extra
constructors, beans accessors and inheritance that the PDF only draws. Reading
those signatures with the bundled ``javap`` keeps the contract closer to what
the local judge actually calls, without guessing member names. Classes that
declare ``main`` are not adopted; they are returned as local checkers so the
solver can run them after compiling.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
import subprocess

from java_assistant.core.spec import Member, Relationship, Specification, Unit
from java_assistant.uml.extract import requirements_for

CONFIDENCE = 0.98
_MAX_CLASSES = 40
_VISIBILITIES = frozenset({"public", "protected", "private"})
_MEMBER_MODIFIERS = frozenset({"static", "final", "abstract"})
_SKIPPED_MODIFIERS = frozenset(
    {"native", "synchronized", "volatile", "transient", "strictfp", "default"}
)
_HEADER = re.compile(
    r"^(?:(?:public|protected|private)\s+)?(?:(?:abstract|final|static)\s+)*"
    r"(class|interface|enum)\s+([\w$]+)"
    r"(?:\s+extends\s+([\w.$]+))?"
    r"(?:\s+implements\s+(.+?))?\s*\{?$"
)
_IDENTIFIER = re.compile(r"^[A-Za-z_$][\w$]*$")


def _clean(text: str) -> str:
    return text.replace("java.lang.", "").strip()


def _split_modifiers(text: str) -> tuple[str, tuple[str, ...], str]:
    visibility = "package"
    modifiers: list[str] = []
    rest = text.strip()
    while True:
        head, separator, tail = rest.partition(" ")
        if not separator or head not in _VISIBILITIES | _MEMBER_MODIFIERS | _SKIPPED_MODIFIERS:
            break
        if head in _VISIBILITIES:
            visibility = head
        elif head in _MEMBER_MODIFIERS:
            modifiers.append(head)
        rest = tail.strip()
    return visibility, tuple(modifiers), rest


def _parameters(raw: str) -> tuple[tuple[str, str], ...]:
    # shortcut: generic types with an internal comma would be split; upgrade to a
    # real signature parser if an exercise ever needs parameterized types.
    pieces = [piece.strip() for piece in raw.split(",") if piece.strip()]
    return tuple((f"arg{index}", _clean(piece)) for index, piece in enumerate(pieces, 1))


def _member(line: str, owner: str) -> Member | None:
    visibility, modifiers, rest = _split_modifiers(line.rstrip(";"))
    if not rest:
        return None
    if rest.endswith(")"):
        head, separator, raw = rest.partition("(")
        if not separator:
            return None
        words = head.split()
        if not words:
            return None
        if len(words) == 1 and words[0] == owner:
            return Member(
                name=owner,
                kind="constructor",
                type_name=owner,
                visibility=visibility,
                parameters=_parameters(raw[:-1]),
                modifiers=modifiers,
            )
        if len(words) < 2:
            return None
        if not words[-1].isidentifier():
            return None
        return Member(
            name=words[-1],
            kind="method",
            type_name=_clean(" ".join(words[:-1])),
            visibility=visibility,
            parameters=_parameters(raw[:-1]),
            modifiers=modifiers,
        )
    words = rest.rsplit(" ", 1)
    if len(words) != 2 or not words[1].isidentifier():
        return None
    return Member(
        name=words[1],
        kind="field",
        type_name=_clean(words[0]),
        visibility=visibility,
        modifiers=modifiers,
    )


def _parse(name: str, output: str) -> tuple[Unit | None, str | None, tuple[str, ...]] | None:
    header: re.Match[str] | None = None
    members: list[Member] = []
    for raw in output.splitlines():
        line = raw.strip()
        if header is None:
            header = _HEADER.match(line)
            continue
        if not line or line == "}":
            continue
        member = _member(line, name)
        if member is not None:
            members.append(member)
    if header is None or header.group(2) != name:
        return None
    has_main = any(
        member.kind == "method"
        and member.name == "main"
        and "static" in member.modifiers
        for member in members
    )
    if has_main:
        return None, None, ()
    modifiers = tuple(
        value for value in ("abstract", "final") if value in header.group(0).split()
    )
    parent = header.group(3).split(".")[-1] if header.group(3) else None
    interfaces = tuple(
        item.split(".")[-1].strip()
        for item in (header.group(4) or "").split(",")
        if item.strip()
    )
    return Unit(name, header.group(1), tuple(members), modifiers, CONFIDENCE), parent, interfaces


def _mentions(text: str, name: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text, re.IGNORECASE))


def _member_key(member: Member) -> tuple[str, str, tuple[str, ...]]:
    return (member.name, member.kind, tuple(kind for _, kind in member.parameters))


class LocalClassAdopter:
    def __init__(
        self,
        root: Path,
        javap: Path | str = "javap",
        timeout_s: int = 10,
    ) -> None:
        self.root = root.resolve(strict=True)
        self.javap = str(javap)
        self.timeout_s = timeout_s

    def adopt(
        self, spec: Specification, text: str, source: str
    ) -> tuple[Specification, tuple[str, ...], tuple[str, ...]]:
        """Returns the completed spec, adopted unit names and local checker names."""
        candidates: dict[str, Path] = {}
        for path in sorted(self.root.rglob("*.class")):
            name = path.stem
            if "$" in name or not _IDENTIFIER.match(name) or not _mentions(text, name):
                continue
            depth = len(path.relative_to(self.root).parts)
            current = candidates.get(name)
            if current is None or depth < len(current.relative_to(self.root).parts):
                candidates[name] = path.parent
            if len(candidates) >= _MAX_CLASSES:
                break
        if not candidates:
            return spec, (), ()

        units: list[Unit] = []
        checkers: list[str] = []
        relationships: list[Relationship] = []
        for name, directory in candidates.items():
            inspected = self._inspect(name, directory)
            if inspected is None:
                continue
            unit, parent, interfaces = inspected
            if unit is None:
                checkers.append(name)
                continue
            units.append(unit)
            if parent:
                relationships.append(Relationship(parent, name, "inheritance", CONFIDENCE))
            for interface in interfaces:
                relationships.append(Relationship(interface, name, "implements", CONFIDENCE))
        if not units:
            return spec, (), tuple(checkers)
        return (
            self._merge(spec, units, relationships, text, source),
            tuple(unit.name for unit in units),
            tuple(checkers),
        )

    def _inspect(self, name: str, directory: Path) -> tuple[Unit | None, str | None, tuple[str, ...]] | None:
        try:
            result = subprocess.run(
                [self.javap, "-p", "-classpath", str(directory), name],
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_s,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return _parse(name, result.stdout)

    @staticmethod
    def _merge(
        spec: Specification,
        units: list[Unit],
        relationships: list[Relationship],
        text: str,
        source: str,
    ) -> Specification:
        by_name = {unit.name: unit for unit in spec.units}
        order = [unit.name for unit in spec.units]
        for local in units:
            existing = by_name.get(local.name)
            if existing is None:
                by_name[local.name] = local
                order.append(local.name)
                continue
            members = list(existing.members)
            positions = {_member_key(member): index for index, member in enumerate(members)}
            for member in local.members:
                key = _member_key(member)
                if key in positions:
                    members[positions[key]] = member
                else:
                    positions[key] = len(members)
                    members.append(member)
            by_name[local.name] = replace(
                existing,
                members=tuple(members),
                confidence=max(existing.confidence, CONFIDENCE),
            )
        merged_units = tuple(by_name[name] for name in order)

        replaced = {(item.child, item.kind) for item in relationships}
        resolved = {(item.parent, item.child) for item in relationships}
        kept = [
            item
            for item in spec.relationships
            if (item.child, item.kind) not in replaced
            and not (item.alternatives and (item.parent, item.child) in resolved)
        ]
        seen = {(item.parent, item.child, item.kind) for item in kept}
        for item in relationships:
            key = (item.parent, item.child, item.kind)
            if key not in seen:
                seen.add(key)
                kept.append(item)

        warnings = tuple(
            dict.fromkeys(
                (
                    *spec.warnings,
                    "Membros e hierarquia adotados de classes compiladas já presentes "
                    "na pasta; confira com o enunciado.",
                )
            )
        )
        requirements = (
            requirements_for(text, merged_units, source)
            if text.strip()
            else spec.requirements
        )
        return Specification(merged_units, tuple(kept), requirements, warnings)


__all__ = ["CONFIDENCE", "LocalClassAdopter"]
