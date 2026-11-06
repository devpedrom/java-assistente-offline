"""Contract trust, confirmation, generation order and the staged solver."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
from typing import Protocol

from .budget import ContextBudget, ContextBudgetError, apply_budget
from .facts import extract_rules, issues, prompt_section, requirements_section
from .spec import Specification, Unit, find_unit

from ..adapters.base import LanguageAdapter, Toolchain
from ..memory.store import ProjectStore
from ..model.client import Message, ModelReply, ModelProtocolError
from ..review.report import EvidenceReport
from ..workspace.files import Workspace
from ..workspace.history import History


CONFIDENCE_FLOOR = 0.9
_INTAKE_FORMAT = (
    " Formato aceito: 'class Nome' e, nas linhas seguintes, '+ atributo: Tipo' "
    "ou '+ metodo(parametro: Tipo): Tipo'; relações como 'Pai <|-- Filho'. "
    "Em várias linhas, termine com uma linha vazia para aplicar."
)
_EDGE_KINDS = frozenset({"inheritance", "implements"})
_SOFT_KINDS = frozenset({"association", "aggregation", "composition"})
_TYPE_TOKEN = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")


class ContractStatus(str, Enum):
    TRUSTED = "trusted"
    NEEDS_CONFIRMATION = "needs_confirmation"
    NO_CONTRACT = "no_contract"


@dataclass(frozen=True)
class Plan:
    order: tuple[str, ...]
    entry: str | None
    issues: tuple[str, ...]


@dataclass(frozen=True)
class SolveOutcome:
    text: str
    completed: bool


class ModelLike(Protocol):
    def complete(self, messages: list[Message]) -> ModelReply: ...


def classify(spec: Specification) -> ContractStatus:
    if not spec.units:
        return ContractStatus.NO_CONTRACT
    names = {unit.name for unit in spec.units}
    weak = (
        any(unit.confidence < CONFIDENCE_FLOOR or not unit.members for unit in spec.units)
        or any(
            requirement.confidence < CONFIDENCE_FLOOR
            for requirement in spec.requirements
        )
        or any(
            relationship.alternatives
            or relationship.confidence < CONFIDENCE_FLOOR
            or relationship.parent not in names
            or relationship.child not in names
            for relationship in spec.relationships
        )
    )
    return ContractStatus.NEEDS_CONFIRMATION if weak else ContractStatus.TRUSTED


def plan(spec: Specification) -> Plan:
    issues: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []
    for unit in spec.units:
        if unit.name in seen and unit.name not in duplicates:
            duplicates.append(unit.name)
        seen.add(unit.name)
    if duplicates:
        issues.append("Unidade duplicada no contrato: " + ", ".join(duplicates) + ".")

    remaining = set(seen)
    edges = {
        (relationship.parent, relationship.child)
        for relationship in spec.relationships
        if relationship.kind in _EDGE_KINDS
        and relationship.parent in seen
        and relationship.child in seen
    }
    soft = {
        (relationship.parent, relationship.child)
        for relationship in spec.relationships
        if relationship.kind in _SOFT_KINDS
        and relationship.parent in seen
        and relationship.child in seen
        and relationship.parent != relationship.child
    }
    for unit in spec.units:
        for member in unit.members:
            types = [member.type_name]
            types.extend(type_name for _, type_name in member.parameters)
            for declared in types:
                for type_name in _TYPE_TOKEN.findall(declared):
                    if type_name in seen and type_name != unit.name:
                        soft.add((type_name, unit.name))
    order: list[str] = []
    while remaining:
        ready = sorted(
            name
            for name in remaining
            if not any(
                child == name and parent in remaining for parent, child in edges
            )
        )
        if not ready:
            issues.append(
                "Ciclo de herança detectado entre: "
                + ", ".join(sorted(remaining))
                + "."
            )
            order.extend(sorted(remaining))
            break
        preferred = [
            name
            for name in ready
            if not any(
                child == name and parent in remaining for parent, child in soft
            )
        ]
        batch = preferred or ready
        order.extend(batch)
        remaining.difference_update(batch)

    entries = sorted(
        {
            unit.name
            for unit in spec.units
            if any(
                member.name == "main"
                and member.kind == "method"
                and "static" in member.modifiers
                for member in unit.members
            )
        }
    )
    if len(entries) > 1:
        issues.append("Entrada ambígua: " + ", ".join(entries) + ".")
    return Plan(tuple(order), entries[0] if entries else None, tuple(issues))


def confirmation_text(spec: Specification, status: ContractStatus) -> str:
    if status is ContractStatus.NO_CONTRACT:
        return (
            "Não há contrato confiável: nenhuma unidade foi identificada no material "
            "selecionado. Envie o PDF do enunciado ou informe as classes, atributos, "
            "métodos e relações." + _INTAKE_FORMAT + " Nada foi gerado nem compilado."
        )
    detail = (
        " Unidades inferidas: " + ", ".join(unit.name for unit in spec.units) + "."
        if spec.units
        else ""
    )
    issues = plan(spec).issues
    if issues:
        detail += " " + " ".join(issues)
    return (
        "Não há contrato confiável: a estrutura inferida tem baixa confiança, relação "
        "ambígua ou unidade sem membros. Confirme classes, atributos, métodos e "
        "heranças antes de gerar." + detail + _INTAKE_FORMAT
        + " Nada foi gerado nem compilado."
    )


class Solver:
    def __init__(
        self,
        *,
        spec: Specification,
        adapter: LanguageAdapter,
        toolchain: Toolchain,
        model: ModelLike,
        workspace: Workspace,
        history: History,
        store: ProjectStore,
        evidence: EvidenceReport,
        budget: ContextBudget,
        criteria: str,
        pdf_text: str = "",
        memory_summary: str = "",
        repair_attempts: int = 2,
        compile_timeout_s: int = 30,
        run_timeout_s: int = 15,
        max_files: int = 40,
        checkers: tuple[str, ...] = (),
    ) -> None:
        if repair_attempts < 0:
            raise ValueError("repair_attempts não pode ser negativo.")
        if max_files < 1:
            raise ValueError("max_files precisa ser positivo.")
        self.spec = spec
        self.adapter = adapter
        self.toolchain = toolchain
        self.model = model
        self.workspace = workspace
        self.history = history
        self.store = store
        self.evidence = evidence
        self.budget = budget
        self.criteria = criteria
        self.pdf_text = pdf_text
        self.memory_summary = memory_summary
        self.repair_attempts = repair_attempts
        self.compile_timeout_s = compile_timeout_s
        self.run_timeout_s = run_timeout_s
        self.max_files = max_files
        self.checkers = tuple(checkers)

    def run(self, request: str, *, confirmed_entry: str | None = None) -> SolveOutcome:
        status = classify(self.spec)
        if status is not ContractStatus.TRUSTED:
            note = (
                "Contrato ausente ou não confiável: nenhum modelo foi chamado e nada "
                "foi compilado."
            )
            self._add_once(self.evidence.observations, note)
            return self._fail(confirmation_text(self.spec, status))

        planned = plan(self.spec)
        if confirmed_entry is not None and confirmed_entry not in planned.order:
            return self._fail(
                f"A entrada {confirmed_entry} não está no plano do contrato; nada foi "
                "gerado nem executado."
            )
        blocking = [
            issue
            for issue in planned.issues
            if not (
                confirmed_entry is not None
                and issue.startswith("Entrada ambígua")
                and confirmed_entry
                in issue.split(":", 1)[1].strip().rstrip(".").split(", ")
            )
        ]
        if blocking:
            return self._fail(
                "O plano do contrato é inválido: "
                + " ".join(blocking)
                + " Nada foi gerado nem compilado."
            )
        if len(planned.order) > self.max_files:
            return self._fail(
                f"O contrato tem {len(planned.order)} unidades, acima do limite de "
                f"{self.max_files} arquivos por execução. Nada foi gerado nem compilado."
            )
        try:
            return self._solve_trusted(request, planned, confirmed_entry)
        except ContextBudgetError as error:
            return self._fail(f"Parei antes de gerar: {error}")

    def _solve_trusted(
        self, request: str, planned: Plan, confirmed_entry: str | None
    ) -> SolveOutcome:
        rules = extract_rules(self.spec)
        if self.checkers and rules:
            self._add_once(
                self.evidence.observations,
                "Há verificador local na pasta: as regras textuais orientam uma "
                "correção e, se ainda falharem, a execução decide.",
            )
        written: set[str] = set()
        for name in planned.order:
            unit = find_unit(self.spec, name)
            assert unit is not None
            error = self._generate_unit(unit, request, rules, "", written)
            if error:
                return self._fail(error)

        sources = self._sources()
        if not sources:
            return self._fail("Nenhuma fonte foi gerada; nada foi compilado.")

        compilation = self.toolchain.compile(sources, timeout_s=self.compile_timeout_s)
        repairs = 0
        while not compilation.success:
            target = self.adapter.repair_target(compilation.diagnostics)
            if target is None:
                return self._fail(
                    "A compilação falhou e o erro não aponta um arquivo corrigível:\n"
                    + compilation.diagnostics[:2000]
                )
            if target not in planned.order:
                return self._fail(
                    f"A compilação falhou em {target}, que não faz parte do plano. "
                    "O arquivo não foi reescrito.\n" + compilation.diagnostics[:2000]
                )
            if repairs >= self.repair_attempts:
                return self._fail(
                    f"A compilação continuou falhando após {repairs} correção(ões) "
                    f"automática(s); parei em {target}:\n"
                    + compilation.diagnostics[:2000]
                )
            unit = find_unit(self.spec, target)
            assert unit is not None
            error = self._generate_unit(
                unit,
                request,
                rules,
                compilation.diagnostics,
                written,
                keep_current=repairs == 0,
            )
            if error:
                return self._fail(error)
            repairs += 1
            compilation = self.toolchain.compile(
                sources, timeout_s=self.compile_timeout_s
            )

        structural = self.adapter.structural_issues(self.spec, self.toolchain)
        structural_repairs = 0
        while structural:
            if structural_repairs >= self.repair_attempts:
                return self._fail(
                    "A validação estrutural continuou falhando após "
                    f"{structural_repairs} correção(ões) automática(s):\n"
                    + "\n".join(structural)
                )
            name = structural[0].split(":", 1)[0].strip()
            unit = find_unit(self.spec, name)
            if unit is None:
                return self._fail(
                    f"A validação estrutural apontou {structural[0]!r}, que não "
                    "identifica uma unidade do plano; nada foi reescrito."
                )
            error = self._generate_unit(
                unit, request, rules, "\n".join(structural), written
            )
            if error:
                return self._fail(error)
            structural_repairs += 1
            compilation = self.toolchain.compile(
                sources, timeout_s=self.compile_timeout_s
            )
            if not compilation.success:
                return self._fail(
                    "A compilação falhou após a correção estrutural:\n"
                    + compilation.diagnostics[:2000]
                )
            structural = self.adapter.structural_issues(self.spec, self.toolchain)

        check_error, checked = self._local_checks(planned, rules, request, written)
        if check_error:
            return self._fail(check_error)

        entry = (
            confirmed_entry
            or self.adapter.entry_point(self.spec)
            or planned.entry
        )
        if entry is not None and entry not in planned.order:
            return self._fail(
                f"A entrada {entry} não está no plano do contrato; nada foi executado."
            )
        if entry is not None:
            result = self.toolchain.run(entry, self.run_timeout_s)
            output = (result.stdout + result.stderr).strip()
            if not result.success:
                timeout = " (tempo esgotado)" if result.timed_out else ""
                self._add_once(
                    self.evidence.unproven,
                    f"A execução de {entry} falhou; o comportamento não foi comprovado.",
                )
                return self._fail(
                    f"A compilação passou, mas a execução de {entry} falhou{timeout} "
                    f"com código {result.returncode}:\n{output[:1500]}"
                )
            self._add_once(
                self.evidence.locally_tested,
                f"java {entry}: encerrou com código 0 "
                "(smoke test sem caso de entrada/saída).",
            )
            self._add_once(
                self.evidence.observations,
                "Entrada/saída não verificada: não há caso explícito com stdin e "
                "expectativa; a execução vale apenas como smoke test.",
            )
        else:
            self._add_once(
                self.evidence.observations,
                "Entrada não executada: nenhuma unidade com main estático no contrato.",
            )

        for source in sources:
            prefix = f"{source} sha256="
            self.evidence.compiled[:] = [
                item for item in self.evidence.compiled if not item.startswith(prefix)
            ]
            self.evidence.compiled.append(
                f"{prefix}{self.workspace.current_hash(source)}"
            )
        foreign = [str(source) for source in sources if str(source) not in written]
        if foreign:
            self._add_once(
                self.evidence.observations,
                "Compilado sem ter sido gerado nesta execução: "
                + ", ".join(foreign)
                + ".",
            )
        if checked:
            self._add_once(
                self.evidence.observations,
                "Regras conferidas pelo verificador já presente na pasta ("
                + ", ".join(checked)
                + "); isso não substitui o juiz da competição.",
            )
        else:
            self._add_once(
                self.evidence.unproven,
                "As regras de negócio não foram comprovadas por testes dos jurados; "
                "compilação e estrutura não as verificam.",
            )
        execution = (
            f"; execução de {entry} apenas como smoke test "
            "(entrada/saída não verificada)"
            if entry is not None
            else "; nenhuma entrada executada"
        )
        rules_status = (
            "As regras de negócio passaram apenas no verificador local da pasta."
            if checked
            else "As regras de negócio não foram comprovadas por testes externos."
        )
        text = (
            f"Solução concluída: {len(planned.order)} arquivo(s) gerado(s) e "
            f"compilados{execution}. {rules_status}"
        )
        self.store.remember("solver", text)
        return SolveOutcome(text, True)

    _CHECK_MARKERS = ("❌", "✘", "✗", "FAIL", "FALHA")
    _PASS_MARKERS = ("✔", "✓")

    @staticmethod
    def _mentions(line: str, name: str) -> bool:
        return bool(re.search(rf"(?<!\w){re.escape(name)}(?!\w)", line))

    def _failing_lines(self, output: str) -> list[str]:
        return [
            line.strip()
            for line in output.splitlines()
            if any(marker in line for marker in self._CHECK_MARKERS)
        ]

    def _has_passed_lines(self, output: str) -> bool:
        return any(line in output for line in self._PASS_MARKERS)

    def _failing_targets(
        self, order: tuple[str, ...], output: str, failing: list[str]
    ) -> tuple[str, ...]:
        """Units named by each failing line, or by the section it belongs to."""
        wanted = set(failing)
        section: str | None = None
        before_section: str | None = None
        last_unit: str | None = None
        found: list[str] = []
        for raw in output.splitlines():
            line = raw.strip()
            named = next((name for name in order if self._mentions(line, name)), None)
            if "──" in line:
                before_section = last_unit
                section = named
            elif named is not None:
                last_unit = named
            if line not in wanted:
                continue
            target = named or section or before_section
            if target is not None and target not in found:
                found.append(target)
        return tuple(found)

    def _run_checker_raw(self, checker: str) -> tuple[bool, str]:
        # A folder checker may start a GUI and fail without a display, so it runs
        # headless first and retries with the usual console flag.
        headless = ("-Djava.awt.headless=true",)
        result = self.toolchain.run(checker, self.run_timeout_s, jvm_args=headless)
        output = (result.stdout + result.stderr).strip()
        if self._failing_lines(output) or self._has_passed_lines(output):
            return result.success, output
        retry = self.toolchain.run(
            checker, self.run_timeout_s, args=("--console",), jvm_args=headless
        )
        return retry.success, (retry.stdout + retry.stderr).strip() or output

    def _run_checker(self, checker: str) -> tuple[bool, str]:
        result = self._run_checker_raw(checker)
        candidates = getattr(self, "_checked_candidates", None)
        if candidates is not None:
            sources = {path: self.workspace.read(path) for path in self._sources()}
            if not any(item[1] == sources for item in candidates):
                results = {
                    name: result if name == checker else self._run_checker_raw(name)
                    for name in self.checkers
                }
                score = self._checker_score(results)
                if score is not None:
                    candidates.append((score, sources))
        return result

    def _checker_score(self, results) -> tuple[int, int] | None:
        passed = failed = 0
        for succeeded, output in results.values():
            failures = self._failing_lines(output)
            passes = sum(
                any(marker in line for marker in self._PASS_MARKERS)
                and not any(marker in line for marker in self._CHECK_MARKERS)
                for line in output.splitlines()
            )
            if (not succeeded and not failures) or not (passes or failures):
                return None
            passed += passes
            failed += len(failures)
        return passed, -failed

    def _local_checks(
        self, planned: Plan, rules, request: str, written: set[str]
    ) -> tuple[str | None, tuple[str, ...]]:
        self._checked_candidates = []
        try:
            try:
                error, passed = self._repair_local_checks(planned, rules, request, written)
            except (ContextBudgetError, ModelProtocolError) as failure:
                error, passed = f"Parei durante o reparo: {failure}", ()
            if not error and len(self.checkers) > 1:
                final = {name: self._run_checker_raw(name) for name in self.checkers}
                if any(not ok or self._failing_lines(output) or not self._has_passed_lines(output)
                       for ok, output in final.values()):
                    error = "Um verificador anterior regrediu após os reparos; a bateria completa não passou."
                    passed = ()
                    self.evidence.locally_tested.clear()
            if not error:
                return error, passed
            self.evidence.locally_tested.clear()
            current = {path: self.workspace.read(path) for path in self._sources()}
            if self.checkers and not any(item[1] == current for item in self._checked_candidates):
                compilation = self.toolchain.compile(self._sources(), timeout_s=self.compile_timeout_s)
                if compilation.success and not self.adapter.structural_issues(self.spec, self.toolchain):
                    self._run_checker(self.checkers[0])
                    latest = next((item for item in self._checked_candidates if item[1] == current), None)
                    if latest is not None and latest[0][1] == 0:
                        for name in self.checkers:
                            self._add_once(self.evidence.locally_tested,
                                           f"{name}: verificador local da pasta aprovou a bateria.")
                        return None, self.checkers
            if not self._checked_candidates:
                return error, passed
            score, sources = max(self._checked_candidates, key=lambda item: item[0])
            if all(self.workspace.read(path) == text for path, text in sources.items()):
                return error, passed
            for path, text in sources.items():
                if self.workspace.read(path) != text:
                    self.history.record(self.workspace.write(path, text))
            compilation = self.toolchain.compile(
                self._sources(), timeout_s=self.compile_timeout_s
            )
            self.evidence.locally_tested.clear()
            self.evidence.compiled.clear()
            if not compilation.success:
                return error + "\nO candidato restaurado não recompilou:\n" + compilation.diagnostics, ()
            structural = self.adapter.structural_issues(self.spec, self.toolchain)
            results = {name: self._run_checker_raw(name) for name in self.checkers}
            if structural or self._checker_score(results) != score:
                return error + "\nO candidato restaurado não repetiu a validação anterior.", ()
            for path in sources:
                self.evidence.compiled.append(
                    f"{path} sha256={self.workspace.current_hash(path)}"
                )
            self._add_once(
                self.evidence.observations,
                f"Melhor candidato restaurado, recompilado e reavaliado: "
                f"{score[0]} linha(s) aprovada(s), {-score[1]} reprovada(s). "
                "A contagem é um indicador local, não comprova correção completa.",
            )
            failures = "\n".join(
                f"{name}:\n" + "\n".join(self._failing_lines(output))
                for name, (_, output) in results.items() if self._failing_lines(output)
            )
            return (
                error.splitlines()[0]
                + "\nO melhor candidato foi restaurado; ainda há falhas locais."
                + f"\nReavaliação do candidato restaurado: {score[0]} aprovada(s), {-score[1]} reprovada(s)."
                + "\n" + failures
            ), ()
        finally:
            del self._checked_candidates

    def _repair_local_checks(
        self, planned: Plan, rules, request: str, written: set[str]
    ) -> tuple[str | None, tuple[str, ...]]:
        passed: list[str] = []
        repairs = 0
        for checker in self.checkers:
            while True:
                regressed = self.adapter.structural_issues(self.spec, self.toolchain)
                if regressed:
                    origin = "A estrutura deixou de conferir"
                    lines = list(regressed)
                    name = lines[0].split(":", 1)[0].strip()
                    targets = (name,) if name in planned.order else ()
                else:
                    succeeded, output = self._run_checker(checker)
                    failing = self._failing_lines(output)
                    if not failing and not succeeded:
                        return (
                            f"O verificador local {checker} não terminou com sucesso e "
                            "não informou qual classe revisar; nada foi reescrito:\n"
                            + output[-1500:],
                            tuple(passed),
                        )
                    if not failing and not self._has_passed_lines(output):
                        return (
                            f"O verificador local {checker} não apresentou nenhuma linha "
                            "de conferência; nada foi comprovado:\n" + output[-1500:],
                            tuple(passed),
                        )
                    if not failing:
                        self._add_once(
                            self.evidence.locally_tested,
                            f"{checker}: verificador local da pasta aprovou a bateria.",
                        )
                        passed.append(checker)
                        break
                    origin = f"O verificador local {checker} reprovou"
                    lines = list(failing)
                    targets = self._failing_targets(planned.order, output, failing)
                if not targets:
                    return (
                        f"{origin} sem apontar uma classe do plano; nada foi "
                        "reescrito:\n" + "\n".join(lines[:10]),
                        tuple(passed),
                    )
                diagnostic = "\n".join(lines)
                if any(
                    re.search(r"exce[çc]|exception", line, re.IGNORECASE)
                    for line in lines
                ):
                    diagnostic += (
                        "\nSe o verificador espera uma exceção, valide também no "
                        "construtor com parâmetros, não só no setter."
                    )
                for target in targets:
                    if repairs >= self.repair_attempts:
                        return (
                            f"{origin} após {repairs} correção(ões) automática(s):\n"
                            + "\n".join(lines[:10]),
                            tuple(passed),
                        )
                    unit = find_unit(self.spec, target)
                    assert unit is not None
                    unit_diagnostic = diagnostic
                    textual = self._textual_issues(unit, rules)
                    if textual:
                        unit_diagnostic += (
                            "\nREGRAS DO ENUNCIADO AINDA NÃO ATENDIDAS:\n"
                            + "\n".join(textual)
                        )
                    error = self._generate_unit(
                        unit, request, rules, unit_diagnostic, written
                    )
                    if error:
                        return error, tuple(passed)
                    repairs += 1
                    compilation = self.toolchain.compile(
                        self._sources(), timeout_s=self.compile_timeout_s
                    )
                    if not compilation.success:
                        return (
                            f"A compilação falhou após a correção pedida por {checker}:\n"
                            + compilation.diagnostics[:2000],
                            tuple(passed),
                        )
        return None, tuple(passed)

    def _textual_issues(self, unit: Unit, rules) -> tuple[str, ...]:
        """Extracted rules still unmet by the unit's current source."""
        relative = Path(f"{unit.name}{self.adapter.source_extension}")
        if not (self.workspace.root / relative).is_file():
            return ()
        return issues(
            rules,
            unit,
            self.workspace.read(relative),
            self.adapter.matchers(),
            self._parent_unit(unit),
        )

    def _parent_unit(self, unit: Unit) -> Unit | None:
        parent = next(
            (
                relationship.parent
                for relationship in self.spec.relationships
                if relationship.kind == "inheritance" and relationship.child == unit.name
            ),
            None,
        )
        return find_unit(self.spec, parent) if parent is not None else None

    def _sources(self) -> list[Path]:
        return sorted(
            path.relative_to(self.workspace.root)
            for path in self.workspace.root.rglob(
                f"*{self.adapter.source_extension}"
            )
            if path.is_file()
        )

    def _parent_sources(self, unit: Unit) -> str:
        names: list[str] = []
        for relationship in self.spec.relationships:
            if (
                relationship.child == unit.name
                and relationship.kind in _EDGE_KINDS
                and relationship.confidence >= CONFIDENCE_FLOOR
            ):
                names.append(relationship.parent)
        # A class that stores or receives another one needs its public API to
        # avoid touching private fields; only files already generated are shown.
        for member in unit.members:
            if member.kind == "field":
                names.append(member.type_name)
            elif member.kind == "method":
                names.append(member.type_name)
            names.extend(type_name for _, type_name in member.parameters)
        parts: list[str] = []
        for name in dict.fromkeys(names):
            name = name.replace("[]", "").strip()
            if name == unit.name or find_unit(self.spec, name) is None:
                continue
            path = Path(f"{name}{self.adapter.source_extension}")
            if not (self.workspace.root / path).is_file():
                continue
            parts.append(
                f"ARQUIVO: {path.as_posix()}\n```\n"
                f"{self.workspace.read(path)}\n```"
            )
        return "\n\n".join(parts)

    def _parent_constructor_hint(self, unit: Unit, diagnostic: str) -> str:
        """A constructor mismatch is fixed only if the model sees the parent's signature."""
        normalized = diagnostic.casefold()
        if (
            "constructor" not in normalized
            and "not applicable" not in normalized
            and "super(" not in normalized
        ):
            return ""
        parent = next(
            (
                relationship.parent
                for relationship in self.spec.relationships
                if relationship.kind == "inheritance" and relationship.child == unit.name
            ),
            None,
        )
        parent_unit = find_unit(self.spec, parent) if parent is not None else None
        if parent_unit is None:
            return ""
        child_constructor = next(
            (
                member
                for member in unit.members
                if member.kind == "constructor"
            ),
            None,
        )
        signatures: list[str] = []
        for member in parent_unit.members:
            if member.kind != "constructor" or not member.parameters:
                continue
            parameters = self._parent_parameter_names(parent_unit, member)
            typed = ", ".join(
                f"{name}: {type_name}" for name, type_name in parameters
            )
            arguments = self._super_arguments(member, child_constructor, parameters)
            signatures.append(f"super({', '.join(arguments)})  // {parent_unit.name}({typed})")
        if not signatures:
            return ""
        return (
            f"\nCONSTRUTOR DA SUPERCLASSE {parent_unit.name}: a primeira linha do "
            "construtor precisa ser uma destas chamadas, com os argumentos na ORDEM "
            "da assinatura do pai: " + " ou ".join(signatures)
        )

    @staticmethod
    def _parent_parameter_names(
        parent_unit: Unit, constructor
    ) -> tuple[tuple[str, str], ...]:
        """javap reports arg1/arg2; the parent's fields carry the real meaning."""
        fields = [member for member in parent_unit.members if member.kind == "field"]
        used: set[str] = set()
        mapped: list[tuple[str, str]] = []
        for position, (name, type_name) in enumerate(constructor.parameters):
            if not re.fullmatch(r"arg\d+", name):
                mapped.append((name, type_name))
                used.add(name)
                continue
            same_type = [
                field
                for field in fields
                if field.type_name == type_name and field.name not in used
            ]
            positional = (
                fields[position]
                if position < len(fields)
                and fields[position].type_name == type_name
                and fields[position].name not in used
                else None
            )
            chosen = positional or (same_type[0] if same_type else None)
            if chosen is None:
                mapped.append((name, type_name))
                continue
            mapped.append((chosen.name, type_name))
            used.add(chosen.name)
        return tuple(mapped)

    @staticmethod
    def _super_arguments(
        parent_constructor, child_constructor, parameters=None
    ) -> tuple[str, ...]:
        """Reuse the child's own parameter names, matched by the parent's types."""
        parameters = tuple(parameters or parent_constructor.parameters)
        synthetic_child = child_constructor is None or all(
            re.fullmatch(r"arg\d+", name)
            for name, _ in child_constructor.parameters
        )
        if synthetic_child:
            return tuple(name for name, _ in parameters)
        available = list(child_constructor.parameters)
        arguments: list[str] = []
        for name, type_name in parameters or parent_constructor.parameters:
            named = next(
                (
                    position
                    for position, (candidate, candidate_type) in enumerate(available)
                    if candidate == name and candidate_type == type_name
                ),
                None,
            )
            if named is not None:
                arguments.append(available.pop(named)[0])
                continue
            index = next(
                (
                    position
                    for position, (_, candidate) in enumerate(available)
                    if candidate == type_name
                ),
                None,
            )
            if index is None:
                arguments.append(name)
            else:
                arguments.append(available.pop(index)[0])
        return tuple(arguments)

    def _unit_diagnostics(self, diagnostic: str, unit: Unit) -> str:
        """Only this unit's javac blocks; other files' errors would mislead the model."""
        blocks = re.split(r"(?m)^(?=.+?\.java:\d+:)", diagnostic)
        marker = f"{unit.name}{self.adapter.source_extension}:"
        selected = [
            block
            for block in blocks
            if block.splitlines() and marker in block.splitlines()[0]
        ]
        return "\n".join(selected).strip() or diagnostic

    def _unit_prompt(
        self, unit: Unit, request: str, rules, diagnostic: str, keep_current: bool
    ) -> list[Message]:
        user_request = request
        if diagnostic:
            diagnostic = self._unit_diagnostics(diagnostic, unit)
            current = ""
            target_path = Path(f"{unit.name}{self.adapter.source_extension}")
            if keep_current and (self.workspace.root / target_path).is_file():
                current = (
                    f"\n\nARQUIVO ATUAL, CORRIJA-O:\n```\n"
                    f"{self.workspace.read(target_path)}\n```"
                )
            hint = self.adapter.diagnostic_hint(diagnostic)
            constructors = self._parent_constructor_hint(unit, diagnostic)
            rewrite = (
                ""
                if keep_current
                else "\n\nReescreva o arquivo do zero; não copie o anterior."
            )
            signatures = self.adapter.unit_contract(self.spec, unit)
            user_request = (
                f"{request}\n\nERRO DA VERIFICAÇÃO ANTERIOR:\n{diagnostic}\n{hint}"
                f"{constructors}{current}{rewrite}"
                f"\n\nDECLARAÇÕES QUE NÃO PODEM MUDAR:\n{signatures}"
            ).rstrip()
        has_constructor = any(
            member.kind == "constructor" for member in unit.members
        )
        target = "\n\n".join(
            part
            for part in (
                self.adapter.unit_contract(self.spec, unit),
                requirements_section(self.spec, unit),
                ""
                if diagnostic or not has_constructor
                else self._parent_constructor_hint(unit, "constructor").strip(),
            )
            if part
        )
        sections = {
            "protocol": self.adapter.system_protocol(),
            "criteria": self.criteria,
            "spec_target": target,
            "parents": self._parent_sources(unit),
            # A scoped requirement already repeats the unit's statement verbatim.
            # Sending the raw PDF again only spends context and, when the excerpt
            # is truncated, shows the model half of another class's rules.
            "pdf_excerpt": (
                ""
                if any(
                    requirement.scope == unit.name
                    for requirement in self.spec.requirements
                )
                else self.pdf_text
            ),
            "rules": prompt_section(rules, unit),
            "memory": self.memory_summary,
            "user_request": user_request,
        }
        budgeted = apply_budget(sections, self.budget)
        self._note_context(budgeted.omitted, budgeted.truncated)
        return self.adapter.build_unit_prompt(
            spec=self.spec, unit=unit, rules=rules, sections=budgeted.sections
        )

    def _generate_unit(
        self,
        unit: Unit,
        request: str,
        rules,
        diagnostic: str,
        written: set[str],
        keep_current: bool = True,
    ) -> str | None:
        messages = self._unit_prompt(unit, request, rules, diagnostic, keep_current)

        relative = Path(f"{unit.name}{self.adapter.source_extension}")
        last_error = ""
        for attempt in range(2):
            reply = self.model.complete(messages)
            try:
                source = self.adapter.parse_unit_source(reply.content, unit)
            except ValueError as error:
                last_error = str(error)
            else:
                last_error = " ".join(
                    issues(
                        rules,
                        unit,
                        source,
                        self.adapter.matchers(),
                        self._parent_unit(unit),
                    )
                )
                # With a local checker the execution decides, so the textual facts
                # only get one chance to steer the model before the file is kept.
                if not last_error or (self.checkers and attempt == 1):
                    if last_error:
                        self._add_once(
                            self.evidence.unproven,
                            f"{unit.name}: a checagem textual não foi satisfeita "
                            f"({last_error}) e o verificador local decidirá.",
                        )
                    change = self.workspace.write(relative, source)
                    self.history.record(change)
                    written.add(str(relative))
                    return None
            if attempt == 0 and diagnostic:
                messages = self._unit_prompt(unit, request, rules, diagnostic, False)
            messages.append(
                Message(
                    "user",
                    f"A resposta anterior foi rejeitada ({last_error}). Comece de "
                    f"novo e retorne SOMENTE {unit.name}"
                    f"{self.adapter.source_extension} completo, sem explicar e sem "
                    "continuar o texto anterior.",
                )
            )
        return f"Parei ao gerar {relative}: {last_error}"

    def _note_context(self, omitted, truncated) -> None:
        for name in omitted:
            self._add_once(
                self.evidence.context_omitted,
                f"{name}: seção omitida (limite de tokens)",
            )
        for name in truncated:
            self._add_once(
                self.evidence.context_omitted,
                f"{name}: seção acima do teto (limite de tokens)",
            )

    @staticmethod
    def _add_once(target: list[str], text: str) -> None:
        if text not in target:
            target.append(text)

    def _fail(self, text: str) -> SolveOutcome:
        self.store.remember("solver", text[:1000])
        return SolveOutcome(text, False)


__all__ = [
    "ContractStatus",
    "ModelLike",
    "Plan",
    "SolveOutcome",
    "Solver",
    "classify",
    "confirmation_text",
    "plan",
]
