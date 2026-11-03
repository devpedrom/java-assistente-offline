"""Test-only adapter that proves the core does not depend on Java."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Mapping

from java_assistant.core.facts import Rule
from java_assistant.core.spec import Specification, Unit
from java_assistant.model.client import Message

from .base import CompileResult, RunResult, Toolchain


class _StubMatchers:
    def factor(self, value: float) -> re.Pattern[str]:
        return re.compile(rf"(?:\*|\*=)\s*{re.escape(str(value))}\b")

    def upper_bound_guard(self) -> re.Pattern[str]:
        return re.compile(r">")

    def super_call(self, method: str) -> re.Pattern[str]:
        return re.compile(rf"super\.{re.escape(method)}\s*\(")

    def arithmetic_on_super(self, method: str) -> re.Pattern[str]:
        return re.compile(rf"super\.{re.escape(method)}\s*\([^)]*\)\s*[-+*/]")


class StubToolchain:
    def __init__(self) -> None:
        self.compiled: list[list[Path]] = []
        self.runs: list[str] = []

    def compile(self, sources, timeout_s: int = 30) -> CompileResult:
        self.compiled.append(list(sources))
        return CompileResult(True, "", Path.cwd(), ("stub",))

    def run(self, main_class: str, timeout_s: int, args=(), stdin: str = "") -> RunResult:
        self.runs.append(main_class)
        return RunResult(True, stdin, "", 0, False)

    def inspect(self, symbol: str, timeout_s: int = 10) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, "", "")


class StubAdapter:
    id = "stub"
    source_extension = ".txt"

    def system_protocol(self) -> str:
        return "Responda com o conteúdo da unidade."

    def unit_contract(self, spec: Specification, unit: Unit) -> str:
        return f"{unit.kind} {unit.name}"

    def build_unit_prompt(
        self,
        *,
        spec: Specification,
        unit: Unit,
        rules: tuple[Rule, ...],
        sections: Mapping[str, str],
    ) -> list[Message]:
        return [
            Message("system", sections.get("protocol", "")),
            Message("user", sections.get("user_request", unit.name)),
        ]

    def parse_unit_source(self, reply: str, unit: Unit) -> str:
        if not reply.strip():
            raise ValueError(f"Resposta vazia para {unit.name}.")
        return reply.strip() + "\n"

    def structural_issues(
        self, spec: Specification, toolchain: Toolchain
    ) -> tuple[str, ...]:
        return ()

    def repair_target(self, diagnostics: str) -> str | None:
        return None

    def diagnostic_hint(self, diagnostics: str) -> str:
        return ""

    def entry_point(self, spec: Specification) -> str | None:
        return spec.units[0].name if spec.units else None

    def matchers(self) -> _StubMatchers:
        return _StubMatchers()
