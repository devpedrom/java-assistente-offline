"""Small deterministic runner for local behavioral checks."""

from __future__ import annotations

from dataclasses import dataclass

from .toolchain import JavaToolchain, RunResult


@dataclass(frozen=True)
class JavaTestCase:
    name: str
    main_class: str
    expected_stdout: str
    stdin: str = ""
    args: tuple[str, ...] = ()
    timeout_s: int = 5


@dataclass(frozen=True)
class JavaTestResult:
    case: JavaTestCase
    passed: bool
    execution: RunResult


class JavaTester:
    def __init__(self, toolchain: JavaToolchain) -> None:
        self.toolchain = toolchain

    def run_case(self, case: JavaTestCase) -> JavaTestResult:
        execution = self.toolchain.run(
            case.main_class,
            timeout_s=case.timeout_s,
            args=case.args,
            stdin=case.stdin,
        )
        passed = execution.success and execution.stdout.strip() == case.expected_stdout.strip()
        return JavaTestResult(case, passed, execution)
