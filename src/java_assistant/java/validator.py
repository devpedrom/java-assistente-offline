"""Compilation-backed validation of a Java UML contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from java_assistant.uml.models import JavaContract, JavaMember

from .toolchain import CompileResult, JavaToolchain


@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    issues: tuple[str, ...]
    compilation: CompileResult


def _signature(owner: str, member: JavaMember) -> str:
    parameters = ",".join(type_name for _, type_name in member.parameters)
    if member.name == owner:
        return f"{member.visibility} {owner}({parameters});"
    return f"{member.visibility} {member.type_name} {member.name}({parameters});"


class ContractValidator:
    def __init__(self, toolchain: JavaToolchain) -> None:
        self.toolchain = toolchain

    def validate(self, contract: JavaContract, root: Path) -> ValidationReport:
        resolved_root = root.resolve(strict=True)
        sources = [path.relative_to(resolved_root) for path in sorted(resolved_root.rglob("*.java"))]
        compilation = self.toolchain.compile(sources)
        if not compilation.success:
            return ValidationReport(False, (compilation.diagnostics,), compilation)

        issues: list[str] = []
        for expected_class in contract.classes:
            inspected = self.toolchain.inspect(expected_class.name)
            if inspected.returncode != 0:
                issues.append(f"Classe ausente: {expected_class.name}")
                continue
            output = " ".join(inspected.stdout.split()).replace("java.lang.", "")
            for field in expected_class.fields:
                fragment = f"{field.visibility} {field.type_name} {field.name};"
                if fragment not in output:
                    issues.append(f"Campo ausente ou divergente: {expected_class.name}.{field.name}")
            for method in expected_class.methods:
                fragment = _signature(expected_class.name, method)
                if fragment not in output:
                    issues.append(f"Método ausente ou divergente: {expected_class.name}.{method.name}")

        for relationship in contract.relationships:
            if relationship.kind != "inheritance" or relationship.confidence < 0.9:
                continue
            inspected = self.toolchain.inspect(relationship.child)
            declaration = " ".join(inspected.stdout.split()).replace("java.lang.", "")
            if f"extends {relationship.parent}" not in declaration:
                issues.append(
                    f"Herança ausente: {relationship.child} deve estender {relationship.parent}"
                )
        return ValidationReport(not issues, tuple(issues), compilation)
