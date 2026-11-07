"""Hybrid state machine joining chat, PDF evidence and safe local tools."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import re
from typing import Protocol

from .adapters import resolve_adapter
from .adapters.base import LanguageAdapter
from .config import AppConfig
from .core.budget import ContextBudget, ContextBudgetError
from .core.commands import CommandRegistry
from .core.solver import (
    ContractStatus,
    Solver,
    classify,
    confirmation_text,
    plan,
)
from .core.spec import Member, Specification, find_unit
from .criteria import build_context, ensure_criteria, load_criteria
from .java.local_classes import LocalClassAdopter
from .java.toolchain import JavaToolchain
from .memory.store import ProjectStore, pdf_sha256, project_identifier
from .model.actions import Action, ActionValidationError, parse_action
from .model.client import Message, ModelReply
from .pdf.discovery import discover_pdfs
from .pdf.extract import PdfEvidence, PdfExtractor
from .profile import Profile, default_profile
from .review.report import EvidenceReport
from .uml.extract import UmlExtractor
from .workspace.files import PatchMismatchError, Workspace
from .workspace.history import History


class ModelLike(Protocol):
    def complete(self, messages: list[Message]) -> ModelReply: ...


@dataclass(frozen=True)
class SessionReply:
    text: str
    exit_requested: bool = False


class AssistantSession:
    def __init__(
        self,
        *,
        config: AppConfig,
        model: ModelLike,
        pdf_extractor: PdfExtractor,
        toolchain: JavaToolchain,
        criteria_template: Path,
        profile: Profile | None = None,
        adapter: LanguageAdapter | None = None,
    ) -> None:
        self.config = config
        self.model = model
        self.pdf_extractor = pdf_extractor
        self.toolchain = toolchain
        self._profile = profile or default_profile(
            Path(os.environ.get("JAVA_ASSISTANT_HOME", "."))
        )
        self.adapter = adapter or resolve_adapter(self._profile.language_id)
        if self._profile.source_extension != self.adapter.source_extension:
            raise ValueError(
                "A extensão do perfil "
                f"({self._profile.source_extension}) não corresponde ao adaptador "
                f"{self._profile.language_id} ({self.adapter.source_extension})."
            )
        self.commands = CommandRegistry.from_profile(self._profile.commands)
        self.workspace = Workspace(config.project_root)
        self.history = History(self.workspace)
        self.evidence = EvidenceReport()
        self._criteria_path = ensure_criteria(config, criteria_template)
        self._pdf_choices: list[Path] = []
        self._awaiting_pdf_choice = False
        self._awaiting_contract_confirmation = False
        self._contract: Specification | None = None
        self._pdf_text = ""
        self._ambiguities: list[int] = []
        self._checkers: tuple[str, ...] = []
        self._intake_buffer: list[str] = []
        self._store = ProjectStore.open(
            "sem-pdf", project_identifier(config.project_root), config.state_dir
        )

    def close(self) -> None:
        try:
            self._store.close()
        finally:
            close = getattr(self.toolchain, "close", None)
            if close is not None:
                close()

    def _contract_text(self) -> str:
        if self._contract is None:
            return ""
        return json.dumps(
            self._contract.to_dict(), ensure_ascii=False, separators=(",", ":")
        )

    def _budget(self) -> ContextBudget:
        limits = self._profile.limits
        return ContextBudget(
            context_tokens=limits.context_tokens,
            output_tokens=limits.output_tokens,
            chars_per_token=self._profile.context.chars_per_token,
            sections=self._profile.context.sections,
        )

    def _relevant_files(self) -> dict[str, str]:
        selected: dict[str, str] = {}
        remaining = 6_000
        for path in sorted(
            self.config.project_root.rglob(f"*{self.adapter.source_extension}")
        ):
            if len(selected) >= 6 or remaining <= 0:
                break
            try:
                relative = path.resolve(strict=True).relative_to(self.config.project_root)
                content = self.workspace.read(relative)
            except (OSError, ValueError):
                continue
            excerpt = content[:remaining]
            selected[str(relative)] = excerpt
            remaining -= len(excerpt)
        return selected

    def _focused_relevant_files(self, target: str) -> dict[str, str]:
        all_files = self._relevant_files()
        if target == self._main_class_name():
            return all_files
        needed: set[str] = set()
        current = target
        seen: set[str] = set()
        while self._contract and current not in seen:
            seen.add(current)
            relationship = next(
                (item for item in self._contract.relationships if item.child == current),
                None,
            )
            if relationship is None:
                break
            needed.add(
                f"{relationship.parent}{self.adapter.source_extension}"
            )
            current = relationship.parent
        return {
            path: content
            for path, content in all_files.items()
            if Path(path).name in needed
        }

    def _main_class_name(self) -> str | None:
        if self._contract is None:
            return None
        return self.adapter.entry_point(self._contract)

    def _missing_units(self) -> list[str]:
        if self._contract is None:
            return []
        extension = self.adapter.source_extension
        return [
            name
            for name in plan(self._contract).order
            if not (self.config.project_root / f"{name}{extension}").is_file()
        ]

    def _confirmation_question(self) -> str | None:
        if (
            self._contract is None
            or classify(self._contract) is not ContractStatus.NEEDS_CONFIRMATION
        ):
            return None
        names = ", ".join(unit.name for unit in self._contract.units)
        return (
            "A estrutura extraída tem baixa confiança. "
            f"Unidades: {names}. Responda 'sim' para confirmar classes, atributos, "
            "métodos e relações, ou envie o enunciado corrigido."
        )

    def _confirm_contract(self) -> SessionReply:
        assert self._contract is not None
        self._contract = replace(
            self._contract,
            units=tuple(
                replace(unit, confidence=1.0) for unit in self._contract.units
            ),
            relationships=tuple(
                replace(relationship, confidence=1.0)
                for relationship in self._contract.relationships
            ),
            requirements=tuple(
                replace(requirement, confidence=1.0)
                for requirement in self._contract.requirements
            ),
        )
        if classify(self._contract) is not ContractStatus.TRUSTED:
            self.evidence.observations.append(
                "Confirmação do usuário registrada, mas o contrato continuou incompleto."
            )
            return SessionReply(
                "A confirmação foi registrada, mas o contrato continua incompleto: "
                "há unidade sem membros ou relação apontando para unidade inexistente. "
                "Nada será gerado até corrigir o enunciado."
            )
        self.evidence.observations.append("Estrutura confirmada pelo usuário.")
        return SessionReply("Estrutura confirmada. Agora posso gerar o código.")

    @staticmethod
    def _wants_generation(text: str) -> bool:
        normalized = text.casefold()
        return any(
            fragment in normalized
            for fragment in ("resolv", "implement", "crie", "criar", "gere", "gerar", "desenvolv")
        )

    def _named_entry(self, text: str) -> str | None:
        if self._contract is None:
            return None
        issue = next(
            (
                item
                for item in plan(self._contract).issues
                if item.startswith("Entrada ambígua:")
            ),
            None,
        )
        if issue is None:
            return None
        candidates = [
            name.strip().rstrip(".") for name in issue.split(":", 1)[1].split(",")
        ]
        lowered = text.casefold()
        named = [
            name
            for name in candidates
            if re.search(rf"\b{re.escape(name.casefold())}\b", lowered)
        ]
        return named[0] if len(named) == 1 else None

    def _solve(self, text: str) -> SessionReply:
        limits = self._profile.limits
        solver = Solver(
            spec=self._contract,
            adapter=self.adapter,
            toolchain=self.toolchain,
            model=self.model,
            workspace=self.workspace,
            history=self.history,
            store=self._store,
            evidence=self.evidence,
            budget=self._budget(),
            criteria=load_criteria(self.config),
            pdf_text=self._pdf_text,
            memory_summary=self._store.summary(max_chars=1_500),
            repair_attempts=limits.repair_attempts,
            compile_timeout_s=limits.compile_timeout_s,
            run_timeout_s=limits.run_timeout_s,
            max_files=limits.max_files,
            checkers=self._checkers,
        )
        return SessionReply(
            solver.run(text, confirmed_entry=self._named_entry(text)).text
        )

    def _list_pdfs(self) -> SessionReply:
        self._pdf_choices = discover_pdfs(self.config.project_root)
        if not self._pdf_choices:
            return SessionReply("Nenhum PDF foi encontrado na pasta atual.")
        self._awaiting_pdf_choice = True
        lines = ["PDFs encontrados:"]
        lines.extend(f"{index}. {path.name}" for index, path in enumerate(self._pdf_choices, 1))
        lines.append("Digite apenas o número do PDF.")
        return SessionReply("\n".join(lines))

    def _adopt_local_classes(self, text: str, source: str) -> tuple[str, ...]:
        if self._contract is None:
            return ()
        adopter = LocalClassAdopter(
            root=self.config.project_root,
            javap=self._profile.toolchain["inspector"],
            timeout_s=self._profile.limits.inspect_timeout_s,
        )
        self._contract, adopted, checkers = adopter.adopt(self._contract, text, source)
        self._checkers = checkers
        for name in adopted:
            entry = f"Classe {name} (API de classes compiladas na pasta)"
            if entry not in self.evidence.inferred_uml:
                self.evidence.inferred_uml.append(entry)
        if adopted:
            self.evidence.observations.append(
                "Contrato completado por classes compiladas da pasta: "
                + ", ".join(adopted)
                + "."
            )
        if checkers:
            self.evidence.observations.append(
                "Verificador local encontrado na pasta; será executado após compilar: "
                + ", ".join(checkers)
                + "."
            )
        return adopted

    def _select_pdf(self, text: str) -> SessionReply:
        try:
            number = int(text)
        except ValueError:
            return SessionReply("Escolha um PDF digitando apenas o número da lista.")
        if number < 1 or number > len(self._pdf_choices):
            return SessionReply("Número inválido. Escolha um item da lista.")
        self._awaiting_pdf_choice = False
        self._awaiting_contract_confirmation = False
        self._intake_buffer.clear()
        selected = self._pdf_choices[number - 1]
        evidence = self.pdf_extractor.extract(selected)
        self._pdf_text = evidence.text[:12_000]
        self._contract = UmlExtractor().extract(evidence)
        self._adopt_local_classes(evidence.text, evidence.source)
        self._store.close()
        self._store = ProjectStore.open(
            pdf_sha256(selected), project_identifier(self.config.project_root), self.config.state_dir
        )
        self._store.remember("pdf", f"Selecionado: {selected.name}; fonte: {evidence.source}")
        self.evidence.confirmed_pdf.append(f"Arquivo selecionado: {selected.name}")
        self.evidence.confirmed_pdf.append(f"Extração utilizada: {evidence.source}")
        for java_class in self._contract.units:
            self.evidence.inferred_uml.append(f"Classe {java_class.name}")
        self._ambiguities = [
            index
            for index, relationship in enumerate(self._contract.relationships)
            if relationship.confidence < 0.9 and relationship.alternatives
        ]
        summary = ", ".join(item.name for item in self._contract.units) or "nenhuma classe segura"
        if self._ambiguities:
            return SessionReply(
                f"PDF carregado. Classes reconhecidas: {summary}.\n" + self._ambiguity_question()
            )
        confirmation = self._confirmation_question()
        if confirmation:
            self._awaiting_contract_confirmation = True
            return SessionReply(
                f"PDF carregado. Classes reconhecidas: {summary}.\n{confirmation}"
            )
        if classify(self._contract) is ContractStatus.NO_CONTRACT:
            return SessionReply(
                f"PDF carregado. Classes reconhecidas: {summary}.\n"
                + confirmation_text(self._contract, ContractStatus.NO_CONTRACT)
            )
        return SessionReply(f"PDF carregado. Classes reconhecidas: {summary}.")

    @staticmethod
    def _member_key(member: Member) -> tuple[str, str, tuple[str, ...]]:
        return (
            member.name,
            member.kind,
            tuple(type_name for _, type_name in member.parameters),
        )

    @staticmethod
    def _merge_contract(
        base: Specification, addition: Specification
    ) -> Specification:
        units = {unit.name: unit for unit in base.units}
        for unit in addition.units:
            existing = units.get(unit.name)
            if existing is None:
                units[unit.name] = unit
                continue
            # Texto do usuário completa/sobrescreve por nome sem apagar o que ele não citou.
            if not unit.members:
                continue
            members = list(existing.members)
            positions = {
                AssistantSession._member_key(member): index
                for index, member in enumerate(members)
            }
            for member in unit.members:
                key = AssistantSession._member_key(member)
                if key in positions:
                    members[positions[key]] = member
                else:
                    positions[key] = len(members)
                    members.append(member)
            units[unit.name] = replace(unit, members=tuple(members))

        replaced_kinds = {
            (relationship.child, relationship.kind)
            for relationship in addition.relationships
        }
        replaced_pairs = {
            (relationship.parent, relationship.child)
            for relationship in addition.relationships
        }
        relationships = [
            relationship
            for relationship in base.relationships
            if (relationship.child, relationship.kind) not in replaced_kinds
            and not (
                relationship.alternatives
                and (relationship.parent, relationship.child) in replaced_pairs
            )
        ]
        seen_relationships = {
            (relationship.parent, relationship.child, relationship.kind)
            for relationship in relationships
        }
        for relationship in addition.relationships:
            key = (relationship.parent, relationship.child, relationship.kind)
            if key not in seen_relationships:
                seen_relationships.add(key)
                relationships.append(relationship)

        requirements = list(base.requirements)
        seen_requirements = {
            (requirement.text, requirement.scope) for requirement in requirements
        }
        for requirement in addition.requirements:
            key = (requirement.text, requirement.scope)
            if key not in seen_requirements:
                seen_requirements.add(key)
                requirements.append(requirement)

        warnings = () if not base.units else base.warnings
        warnings = tuple(dict.fromkeys((*warnings, *addition.warnings)))
        return Specification(
            tuple(units.values()),
            tuple(relationships),
            tuple(requirements),
            warnings,
        )

    def _queue_intake(self, text: str) -> SessionReply | None:
        if "\n" in text:
            return self._intake_reply(text)
        starts_class = re.match(
            r"^\s*(?:class|classe|interface)\b", text, re.IGNORECASE
        )
        if not self._intake_buffer and not starts_class:
            return None
        if starts_class:
            self._intake_buffer = [text]
        else:
            self._intake_buffer.append(text)
        return SessionReply(
            "Anotei. Continue o texto corrigido e envie uma linha vazia para aplicar."
        )

    def _intake_reply(
        self, text: str, candidate: Specification | None = None
    ) -> SessionReply:
        assert self._contract is not None
        self._intake_buffer.clear()
        candidate = candidate or UmlExtractor().extract(PdfEvidence(text, "user", ()))
        if not candidate.units:
            status = classify(self._contract)
            self._awaiting_contract_confirmation = (
                status is ContractStatus.NEEDS_CONFIRMATION
            )
            return SessionReply(confirmation_text(self._contract, status))
        self._contract = self._merge_contract(self._contract, candidate)
        self.evidence.observations.append(
            "Contrato textual do usuário aplicado: "
            + ", ".join(unit.name for unit in candidate.units)
            + "."
        )
        for unit in candidate.units:
            entry = f"Classe {unit.name} (texto do usuário)"
            if entry not in self.evidence.inferred_uml:
                self.evidence.inferred_uml.append(entry)
        self._ambiguities = [
            index
            for index, relationship in enumerate(self._contract.relationships)
            if relationship.confidence < 0.9 and relationship.alternatives
        ]
        status = classify(self._contract)
        self._awaiting_contract_confirmation = (
            status is ContractStatus.NEEDS_CONFIRMATION
        )
        if self._ambiguities:
            return SessionReply(
                "Contrato atualizado com a resposta textual.\n"
                + self._ambiguity_question()
            )
        if status is ContractStatus.NEEDS_CONFIRMATION:
            return SessionReply(
                "Contrato atualizado com a resposta textual, mas ainda há dados a "
                "confirmar.\n" + confirmation_text(self._contract, status)
            )
        return SessionReply(
            "Contrato atualizado com a resposta textual. Agora posso gerar o código."
        )

    def _ambiguity_question(self) -> str:
        assert self._contract is not None and self._ambiguities
        relationship = self._contract.relationships[self._ambiguities[0]]
        options = "\n".join(
            f"{index}. {name}" for index, name in enumerate(relationship.alternatives, 1)
        )
        return (
            f"Relacionamento ambíguo entre {relationship.parent} e {relationship.child}. "
            f"Escolha uma interpretação:\n{options}"
        )

    def _resolve_ambiguity(self, text: str) -> SessionReply:
        assert self._contract is not None and self._ambiguities
        relationship_index = self._ambiguities[0]
        relationship = self._contract.relationships[relationship_index]
        try:
            choice = int(text) - 1
        except ValueError:
            return SessionReply(self._ambiguity_question())
        if choice < 0 or choice >= len(relationship.alternatives):
            return SessionReply(self._ambiguity_question())
        selected = relationship.alternatives[choice]
        resolved = replace(relationship, kind=selected, confidence=1.0, alternatives=())
        relationships = list(self._contract.relationships)
        relationships[relationship_index] = resolved
        self._contract = replace(self._contract, relationships=tuple(relationships))
        self._ambiguities.pop(0)
        self._store.remember(
            "decision", f"{relationship.parent}-{relationship.child}: {selected}"
        )
        if self._ambiguities:
            return SessionReply(f"Interpretação registrada: {selected}.\n{self._ambiguity_question()}")
        confirmation = self._confirmation_question()
        if confirmation:
            self._awaiting_contract_confirmation = True
            return SessionReply(
                f"Interpretação registrada: {selected}.\n{confirmation}"
            )
        return SessionReply(f"Interpretação registrada: {selected}. Agora posso gerar o código.")

    @staticmethod
    def _text_arg(action: Action, name: str) -> str:
        value = action.args.get(name)
        if not isinstance(value, str):
            raise ValueError(f"Argumento textual obrigatório: {name}")
        return value

    def _execute_action(self, action: Action, *, expected_files: dict[Path, str | None]) -> str:
        if action.tool == "read_file":
            path = self._text_arg(action, "path")
            return self.workspace.read(Path(path))
        if action.tool == "write_file":
            path = self._text_arg(action, "path")
            content = self._text_arg(action, "content")
            change = self.history.write(Path(path), content,
                expected=self.workspace.expected_content(Path(path), expected_files))
            expected_files[change.relative_path] = change.after_hash
            self._store.remember("change", f"Arquivo escrito: {path}")
            return f"Arquivo salvo: {path}"
        if action.tool == "apply_patch":
            path = self._text_arg(action, "path")
            self.workspace.expected_content(Path(path), expected_files)
            change = self.history.write(
                Path(path),
                self._text_arg(action, "replacement"),
                expected=self._text_arg(action, "expected"),
            )
            expected_files[change.relative_path] = change.after_hash
            self._store.remember("change", f"Arquivo ajustado: {path}")
            return f"Arquivo ajustado: {path}"
        if action.tool == "compile_java":
            raw_sources = action.args.get("sources")
            if raw_sources is None:
                sources = [
                    path.relative_to(self.config.project_root)
                    for path in self.config.project_root.rglob(
                        f"*{self.adapter.source_extension}"
                    )
                ]
            elif isinstance(raw_sources, list) and all(isinstance(item, str) for item in raw_sources):
                sources = [Path(item) for item in raw_sources]
            else:
                raise ValueError("sources precisa ser uma lista de caminhos.")
            result = self.toolchain.compile(
                sources, timeout_s=self._profile.limits.compile_timeout_s
            )
            if result.success:
                names = ", ".join(str(item) for item in sources)
                if names not in self.evidence.compiled:
                    self.evidence.compiled.append(names)
                self._store.remember("compile", f"Sucesso: {names}")
                return f"Compilação Java 8 concluída: {names}"
            self._store.remember("compile", f"Falha: {result.diagnostics[:1000]}")
            return f"Falha de compilação:\n{result.diagnostics}"
        if action.tool == "run_java":
            main_class = self._text_arg(action, "main_class")
            requested_timeout = action.args.get("timeout_s", 5)
            timeout_s = max(
                1, min(self._profile.limits.run_timeout_s, int(requested_timeout))
            )
            result = self.toolchain.run(main_class, timeout_s)
            if result.success:
                label = f"{main_class}: smoke test sem entrada/saída verificada"
                if label not in self.evidence.locally_tested:
                    self.evidence.locally_tested.append(label)
                observation = (
                    f"{main_class}: smoke test sem entrada/saída verificada; "
                    "não é validação funcional."
                )
                if observation not in self.evidence.observations:
                    self.evidence.observations.append(observation)
                return (
                    "Execução concluída (smoke test sem entrada/saída verificada). "
                    f"Saída:\n{result.stdout}"
                )
            if result.timed_out:
                return f"Execução interrompida após {timeout_s}s (timeout)."
            return f"Execução falhou ({result.returncode}):\n{result.stderr}"
        if action.tool == "memory":
            content = self._text_arg(action, "content")
            self._store.remember("note", content)
            return "Informação registrada na memória deste projeto."
        if action.tool == "select_pdf":
            return "Use o comando /pdf para selecionar um arquivo com confirmação do usuário."
        raise ValueError("Ação não implementada.")

    def _unverified_warning(self, *, wrote: bool, compiled: bool, ran: bool) -> str:
        if ran:
            return (
                "A execução foi um smoke test sem entrada/saída verificada; "
                "não é validação funcional.\n"
            )
        if not wrote or compiled:
            return ""
        return (
            "Não confirmei a solução: houve escrita sem compilação e execução "
            "aprovadas neste pedido.\n"
        )

    def _chat(self, text: str) -> SessionReply:
        if self._contract is not None and self._wants_generation(text):
            return self._solve(text)
        if self._contract is not None:
            status = classify(self._contract)
            if status is not ContractStatus.TRUSTED:
                self._awaiting_contract_confirmation = (
                    status is ContractStatus.NEEDS_CONFIRMATION
                )
                return SessionReply(confirmation_text(self._contract, status))
        initial_missing = self._missing_units()
        focused_target = initial_missing[0] if initial_missing else None
        expected_files = self.workspace.snapshot()
        try:
            messages = build_context(
                criteria=load_criteria(self.config),
                contract="" if focused_target else self._contract_text(),
                source_text="" if focused_target else self._pdf_text,
                memory_summary=self._store.summary(max_chars=1_500),
                relevant_files=(
                    self._focused_relevant_files(focused_target)
                    if focused_target
                    else self._relevant_files()
                ),
                user_request=text,
                budget=self._budget(),
            )
        except ContextBudgetError as error:
            return SessionReply(f"Parei antes de responder: {error}")
        messages[0] = Message(
            "system", messages[0].content + "\n\n" + self.adapter.system_protocol()
        )
        actions_used = 0
        consecutive_failures = 0
        wrote_in_request = False
        compiled_in_request = False
        ran_in_request = False
        compile_failed = False
        while True:
            missing = self._missing_units()
            if missing:
                unit = find_unit(self._contract, missing[0])
                assert unit is not None
                messages.append(
                    Message(
                        "user",
                        f"ETAPA OBRIGATÓRIA AGORA: escreva SOMENTE {missing[0]}"
                        f"{self.adapter.source_extension} com uma única classe. "
                        "Use o bloco <write_file>; não escreva outra classe.\n"
                        + self.adapter.unit_contract(self._contract, unit),
                    )
                )
            elif compile_failed:
                messages.append(
                    Message(
                        "user",
                        "ETAPA OBRIGATÓRIA AGORA: corrija exatamente um arquivo indicado pelo "
                        "erro de compilação anterior. Depois será compilado novamente.",
                    )
                )
            elif wrote_in_request and not compiled_in_request:
                messages.append(Message("user", "ETAPA OBRIGATÓRIA AGORA: responda <compile_java />"))
            elif compiled_in_request and not ran_in_request and self._main_class_name():
                messages.append(
                    Message(
                        "user",
                        "ETAPA OBRIGATÓRIA AGORA: responda "
                        f'<run_java main_class="{self._main_class_name()}" />',
                    )
                )
            elif wrote_in_request:
                messages.append(
                    Message(
                        "user",
                        "ETAPA OBRIGATÓRIA AGORA: responda <respond> com um resumo curto.",
                    )
                )
            reply = self.model.complete(messages)
            try:
                action = parse_action(reply.content)
            except ActionValidationError:
                self._store.remember("assistant", reply.content)
                warning = self._unverified_warning(
                    wrote=wrote_in_request,
                    compiled=compiled_in_request,
                    ran=ran_in_request,
                )
                return SessionReply(warning + reply.content)
            if action.tool == "respond":
                text_reply = self._text_arg(action, "text")
                self._store.remember("assistant", text_reply)
                warning = self._unverified_warning(
                    wrote=wrote_in_request,
                    compiled=compiled_in_request,
                    ran=ran_in_request,
                )
                return SessionReply(warning + text_reply)
            if actions_used >= 12:
                return SessionReply(
                    "Parei após doze ações neste pedido para evitar um ciclo do modelo. "
                    "Revise o estado e peça para continuar."
                )
            actions_used += 1
            try:
                result = self._execute_action(action, expected_files=expected_files)
            except PatchMismatchError as exc:
                self.evidence.compiled.clear()
                self.evidence.locally_tested.clear()
                return SessionReply(f"Parei: {exc}")
            except (OSError, ValueError, PatchMismatchError, RuntimeError) as exc:
                result = f"AÇÃO RECUSADA OU FALHOU: {exc}"
            if action.tool in {"write_file", "apply_patch"}:
                wrote_in_request = wrote_in_request or result.startswith(
                    ("Arquivo salvo", "Arquivo ajustado")
                )
                compiled_in_request = False
                ran_in_request = False
                compile_failed = False
            elif action.tool == "compile_java":
                compiled_in_request = result.startswith(
                    "Compilação Java 8 concluída"
                )
                compile_failed = result.startswith("Falha de compilação")
            elif action.tool == "run_java":
                ran_in_request = result.startswith("Execução concluída")
            failed = result.startswith(("Falha", "AÇÃO RECUSADA", "Execução falhou"))
            consecutive_failures = consecutive_failures + 1 if failed else 0
            if consecutive_failures >= 3:
                return SessionReply(
                    "Parei após três falhas consecutivas. Revise o diagnóstico e peça para continuar."
                )
            messages.append(Message("assistant", reply.content))
            messages.append(Message("user", f"RESULTADO DA AÇÃO:\n{result}"))

    def _profile_text(self) -> str:
        profile = self._profile
        limits = profile.limits
        project = str(profile.project_path) if profile.project_path else "nenhum"
        return "\n".join(
            (
                f"perfil global: {profile.global_path}",
                f"perfil de projeto: {project}",
                f"origem: {profile.origin}",
                f"linguagem: {profile.language_id} ({profile.source_extension})",
                f"limites: contexto {limits.context_tokens} tokens, saída "
                f"{limits.output_tokens}, reparos {limits.repair_attempts}, "
                f"arquivos {limits.max_files}",
                self.commands.help_text(),
            )
        )

    def handle(self, text: str) -> SessionReply:
        stripped = text.strip()
        if not stripped:
            if self._intake_buffer:
                pending = "\n".join(self._intake_buffer)
                self._intake_buffer.clear()
                return self._intake_reply(pending)
            return SessionReply("")
        command = self.commands.resolve(stripped)
        if command == "exit":
            return SessionReply("Até logo.", True)
        if command == "pdf":
            return self._list_pdfs()
        if command == "undo":
            return SessionReply(self.history.undo_last().reason)
        if command == "report":
            return SessionReply(self.evidence.render())
        if command == "profile":
            return SessionReply(self._profile_text())
        if command == "help":
            return SessionReply(self.commands.help_text())
        if self._awaiting_pdf_choice:
            return self._select_pdf(stripped)
        if self._ambiguities:
            if not stripped.isdigit():
                queued = self._queue_intake(stripped)
                if queued is not None:
                    return queued
                return SessionReply("Antes de gerar, escolha uma interpretação.\n" + self._ambiguity_question())
            return self._resolve_ambiguity(stripped)
        if self._awaiting_contract_confirmation:
            if stripped.casefold() in {"sim", "confirmo", "s"}:
                self._awaiting_contract_confirmation = False
                self._intake_buffer.clear()
                return self._confirm_contract()
        if command is None and stripped.startswith("/"):
            return SessionReply(self.commands.help_text())
        if (
            self._contract is not None
            and classify(self._contract) is not ContractStatus.TRUSTED
        ):
            queued = self._queue_intake(stripped)
            if queued is not None:
                return queued
            return self._intake_reply(stripped)
        return self._chat(stripped)
