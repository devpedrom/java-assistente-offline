"""Compilation-backed validation of a language-neutral specification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from java_assistant.core.spec import Member, Specification, members_of

from ..adapters.base import CompileResult, Toolchain
from .toolchain import JavaToolchain


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    issues: tuple[str, ...]
    compilation: CompileResult


def _typed(visibility: str, declaration: str) -> str:
    # javap prints package-private members without any visibility keyword.
    return declaration if visibility == "package" else f"{visibility} {declaration}"


def _signature(owner: str, member: Member) -> str:
    parameters = ", ".join(type_name for _, type_name in member.parameters)
    if member.kind == "constructor":
        return _typed(member.visibility, f"{owner}({parameters});")
    modifiers = "".join(f"{modifier} " for modifier in member.modifiers)
    return _typed(
        member.visibility,
        f"{modifiers}{member.type_name} {member.name}({parameters});",
    )


class ContractValidator:
    def __init__(self, toolchain: JavaToolchain) -> None:
        self.toolchain = toolchain

    def validate(self, spec: Specification, root: Path) -> ValidationReport:
        resolved_root = root.resolve(strict=True)
        sources = [path.relative_to(resolved_root) for path in sorted(resolved_root.rglob("*.java"))]
        compilation = self.toolchain.compile(sources)
        if not compilation.success:
            return ValidationReport(False, (compilation.diagnostics,), compilation)
        issues = contract_issues(spec, self.toolchain)
        return ValidationReport(not issues, issues, compilation)


def contract_issues(
    spec: Specification, toolchain: Toolchain
) -> tuple[str, ...]:
    """Inspect already-compiled symbols without recompiling the project."""
    issues: list[str] = []
    for expected_unit in spec.units:
        inspected = toolchain.inspect(expected_unit.name)
        if inspected.returncode != 0:
            issues.append(f"{expected_unit.name}: classe ausente")
            continue
        output = (
            " ".join(inspected.stdout.split())
            .replace("java.lang.", "")
        )
        if expected_unit.kind == "interface" or "abstract" in expected_unit.modifiers:
            output = output.replace(" abstract ", " ").replace(" final ", " ")
        for field in members_of(expected_unit, "field"):
            modifiers = "".join(f"{modifier} " for modifier in field.modifiers)
            fragment = _typed(
                field.visibility,
                f"{modifiers}{field.type_name} {field.name};",
            )
            if fragment not in output:
                issues.append(
                    f"{expected_unit.name}: campo ausente ou divergente: {field.name}"
                )
        for method in (
            *members_of(expected_unit, "constructor"),
            *members_of(expected_unit, "method"),
        ):
            fragment = _signature(expected_unit.name, method)
            if fragment not in output:
                issues.append(
                    f"{expected_unit.name}: método ausente ou divergente: {method.name}"
                )

    for relationship in spec.relationships:
        if relationship.kind not in {"inheritance", "implements"}:
            continue
        if relationship.confidence < 0.9:
            continue
        inspected = toolchain.inspect(relationship.child)
        declaration = (
            " ".join(inspected.stdout.split())
            .replace("java.lang.", "")
            .replace(" abstract ", " ")
        )
        keyword = "extends" if relationship.kind == "inheritance" else "implements"
        if f"{keyword} {relationship.parent}" not in declaration:
            issues.append(
                f"{relationship.child}: relação ausente; deve usar "
                f"{keyword} {relationship.parent}"
            )
    return tuple(issues)
