"""Language boundary: toolchain results, adapter protocol and source matchers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Mapping, Protocol

from java_assistant.core.facts import Rule, SourceMatchers
from java_assistant.core.spec import Specification, Unit
from java_assistant.model.client import Message


@dataclass(frozen=True)
class CompileResult:
    success: bool
    diagnostics: str
    classes_dir: Path
    command: tuple[str, ...]


@dataclass(frozen=True)
class RunResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int | None
    timed_out: bool


class Toolchain(Protocol):
    def compile(self, sources: list[Path], timeout_s: int = 30) -> CompileResult: ...

    def run(
        self,
        main_class: str,
        timeout_s: int,
        args: tuple[str, ...] = (),
        stdin: str = "",
    ) -> RunResult: ...

    def inspect(self, symbol: str, timeout_s: int = 10) -> subprocess.CompletedProcess[str]: ...


class LanguageAdapter(Protocol):
    id: str
    source_extension: str

    def system_protocol(self) -> str: ...

    def unit_contract(self, spec: Specification, unit: Unit) -> str: ...

    def build_unit_prompt(
        self,
        *,
        spec: Specification,
        unit: Unit,
        rules: tuple[Rule, ...],
        sections: Mapping[str, str],
    ) -> list[Message]: ...

    def parse_unit_source(self, reply: str, unit: Unit) -> str: ...

    # Cada item tem o formato "Unidade: problema" para o solver localizar o alvo.
    def structural_issues(
        self, spec: Specification, toolchain: Toolchain
    ) -> tuple[str, ...]: ...

    def repair_target(self, diagnostics: str) -> str | None: ...

    def diagnostic_hint(self, diagnostics: str) -> str: ...

    def entry_point(self, spec: Specification) -> str | None: ...

    def matchers(self) -> SourceMatchers: ...


__all__ = [
    "CompileResult",
    "LanguageAdapter",
    "Rule",
    "RunResult",
    "SourceMatchers",
    "Toolchain",
]
