"""Independent finite fixture oracles; never imported by the installed product."""

import json
from pathlib import Path

from java_assistant.java.judge import Judge
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.model.client import ModelReply


def check(name, solution, contract, enunciado):
    fixture = Path(__file__).resolve().parents[1] / "fixtures/enunciados/cases" / f"{name}.json"
    if not fixture.is_file():
        return None, "sem oráculo independente para esta fixture"
    class FixtureCases:
        def complete(self, messages, **kwargs):
            return ModelReply(json.dumps({"cases": json.loads(fixture.read_text(encoding="utf-8"))}))
    toolchain = JavaToolchain(solution)
    try:
        judge = Judge(toolchain, FixtureCases())
        cases = judge.build_cases(contract, enunciado)
        report = judge.run(cases)
        if not cases:
            return None, "; ".join(report.unverified)
        if report.failed:
            return False, "; ".join(report.failed)[-2000:]
        return bool(report.passed), f"{len(report.passed)} caso(s) independente(s); cobertura completa não comprovada"
    finally:
        toolchain.close()
