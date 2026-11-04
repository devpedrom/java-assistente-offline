"""Mede a fidelidade do assistente nos enunciados de teste.

Fora da suite padrao: E4/E5 dependem de pdftotext e, com --solucao, de
javac/java para compilar e executar a solucao gerada.

Uso:
    python tests/qualidade/medir.py
    python tests/qualidade/medir.py --fixture E5 --solucao /caminho/da/solucao
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from java_assistant.pdf.extract import PdfEvidence, PdfExtractionError, PdfExtractor
from java_assistant.uml.extract import UmlExtractor
from java_assistant.uml.models import JavaClass, JavaContract, JavaMember, Relationship

ROOT = Path(__file__).resolve().parents[1]
ENUNCIADOS = ROOT / "fixtures" / "enunciados"
EXPECTED = ENUNCIADOS / "expected"
FROTA = ROOT / "fixtures" / "frota"

FIXTURES = (
    ("E1", ENUNCIADOS / "E1.txt"),
    ("E2", ENUNCIADOS / "E2.txt"),
    ("E3", ENUNCIADOS / "E3.txt"),
    ("E4", ENUNCIADOS / "E4.pdf"),
    ("E5", FROTA / "enunciado.pdf"),
)


@dataclass(frozen=True)
class FixtureResult:
    name: str
    contract_ok: bool | None = None
    compiled: bool | None = None
    behavior_ok: bool | None = None
    untouched: bool = True
    reason: str = ""

    @property
    def passed(self) -> bool:
        checks = (self.contract_ok, self.compiled, self.behavior_ok)
        return self.untouched and True in checks and False not in checks


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_expected(name: str) -> tuple[JavaContract, str]:
    import json

    data = json.loads((EXPECTED / f"{name}.json").read_text(encoding="utf-8"))

    def members(items) -> tuple[JavaMember, ...]:
        return tuple(
            JavaMember(
                item["name"],
                item["type_name"],
                item["visibility"],
                tuple(
                    (parameter["name"], parameter["type_name"])
                    for parameter in item.get("parameters", ())
                ),
            )
            for item in items
        )

    classes = tuple(
        JavaClass(item["name"], members(item.get("fields", ())), members(item.get("methods", ())))
        for item in data["classes"]
    )
    relationships = tuple(
        Relationship(
            item["parent"], item["child"], item["kind"], float(item.get("confidence", 1.0))
        )
        for item in data.get("relationships", ())
    )
    return JavaContract(classes, relationships), data.get("contract_scope", "full")


def _shape(contract: JavaContract, scope: str):
    classes = tuple(
        sorted(
            (
                item.name,
                tuple(sorted((field.name, field.type_name, field.visibility) for field in item.fields)),
                tuple(
                    sorted(
                        (method.name, method.type_name, method.visibility, tuple(method.parameters))
                        for method in item.methods
                    )
                ),
            )
            if scope == "full"
            else (item.name,)
            for item in contract.classes
        )
    )
    relationships = tuple(sorted((item.parent, item.child, item.kind) for item in contract.relationships))
    return classes, relationships


def _evidence(path: Path) -> PdfEvidence:
    if path.suffix.casefold() == ".pdf":
        return PdfExtractor().extract(path)
    return PdfEvidence(text=path.read_text(encoding="utf-8"), source="texto", warnings=())


def _compile(solution: Path) -> tuple[bool, Path, str]:
    work = Path(tempfile.mkdtemp(prefix="qualidade-classes-"))
    sources = sorted(solution.glob("*.java"))
    if not sources:
        return False, work, "nenhum .java na solução"
    result = subprocess.run(
        ["javac", "-encoding", "UTF-8", "--release", "8", "-d", str(work), *map(str, sources)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    return result.returncode == 0, work, (result.stdout + result.stderr).strip()


def _validator(classes: Path) -> tuple[bool, str]:
    import os

    command = [
        "java",
        "-cp",
        f"{classes}{os.pathsep}{FROTA}",
        "Frota",
        "--console",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0 and "FALHOU" not in output, output


def run(name: str, solution: Path | None = None) -> FixtureResult:
    path = dict(FIXTURES)[name]
    before = _digest(path)
    expected, scope = _load_expected(name)
    try:
        contract = UmlExtractor().extract(_evidence(path))
    except PdfExtractionError as exc:
        return FixtureResult(name, reason=f"não medido: {exc}")
    result = FixtureResult(
        name,
        contract_ok=_shape(contract, scope) == _shape(expected, scope),
        untouched=_digest(path) == before,
        reason="" if contract.classes else "nenhuma classe reconhecida",
    )
    if solution is None:
        return result
    compiled, classes, diagnostics = _compile(solution)
    if not compiled:
        return FixtureResult(
            result.name, result.contract_ok, False, None, result.untouched, diagnostics or "compilação falhou"
        )
    if name == "E5":
        behavior_ok, output = _validator(classes)
        return FixtureResult(result.name, result.contract_ok, True, behavior_ok, result.untouched, "" if behavior_ok else output[-400:])
    return FixtureResult(result.name, result.contract_ok, True, None, result.untouched, "sem juiz de comportamento")


def _label(value: bool | None) -> str:
    return "não medido" if value is None else ("ok" if value else "FALHOU")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=[name for name, _ in FIXTURES])
    parser.add_argument("--solucao", type=Path)
    arguments = parser.parse_args(argv)

    names = [arguments.fixture] if arguments.fixture else [name for name, _ in FIXTURES]
    results = [run(name, arguments.solucao) for name in names]
    for item in results:
        print(
            f"{item.name}  contrato: {_label(item.contract_ok)}  "
            f"compilado: {_label(item.compiled)}  "
            f"comportamento: {_label(item.behavior_ok)}"
            + (f"  ({item.reason})" if item.reason else "")
        )
    passed = sum(1 for item in results if item.passed)
    print(f"\nFidelidade: {passed} de {len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
