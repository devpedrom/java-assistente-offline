"""Hybrid state machine joining chat, PDF evidence and safe local tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
from typing import Protocol

from .config import AppConfig
from .criteria import build_context, ensure_criteria, load_criteria
from .java.toolchain import JavaToolchain
from .memory.store import ProjectStore, pdf_sha256, project_identifier
from .model.actions import Action, ActionValidationError, parse_action
from .model.client import Message, ModelReply
from .pdf.discovery import discover_pdfs
from .pdf.extract import PdfExtractor
from .review.report import EvidenceReport
from .uml.extract import UmlExtractor
from .uml.models import JavaContract, Relationship
from .workspace.files import PatchMismatchError, Workspace
from .workspace.history import History


class ModelLike(Protocol):
    def complete(self, messages: list[Message]) -> ModelReply: ...


@dataclass(frozen=True)
class SessionReply:
    text: str
    exit_requested: bool = False


_ACTION_PROTOCOL = """
Quando precisar agir, responda SOMENTE com um objeto JSON:
{"tool":"write_file","args":{"path":"Classe.java","content":"..."}}
Ferramentas: read_file, write_file, apply_patch, compile_java, run_java e memory.
Nunca use shell. Use no máximo uma ferramenta por resposta. Quando terminar, responda em português.
""".strip()


class AssistantSession:
    def __init__(
        self,
        *,
        config: AppConfig,
        model: ModelLike,
        pdf_extractor: PdfExtractor,
        toolchain: JavaToolchain,
        criteria_template: Path,
    ) -> None:
        self.config = config
        self.model = model
        self.pdf_extractor = pdf_extractor
        self.toolchain = toolchain
        self.workspace = Workspace(config.project_root)
        self.history = History(self.workspace)
        self.evidence = EvidenceReport()
        self._criteria_path = ensure_criteria(config, criteria_template)
        self._pdf_choices: list[Path] = []
        self._awaiting_pdf_choice = False
        self._contract: JavaContract | None = None
        self._ambiguities: list[int] = []
        self._store = ProjectStore.open(
            "sem-pdf", project_identifier(config.project_root), config.state_dir
        )

    def close(self) -> None:
        self._store.close()

    def _contract_text(self) -> str:
        if self._contract is None:
            return ""
        return json.dumps(asdict(self._contract), ensure_ascii=False, indent=2)

    def _relevant_files(self) -> dict[str, str]:
        selected: dict[str, str] = {}
        for path in sorted(self.config.project_root.rglob("*.java")):
            if len(selected) >= 8:
                break
            try:
                relative = path.resolve(strict=True).relative_to(self.config.project_root)
                content = self.workspace.read(relative)
            except (OSError, ValueError):
                continue
            selected[str(relative)] = content[:20_000]
        return selected

    def _list_pdfs(self) -> SessionReply:
        self._pdf_choices = discover_pdfs(self.config.project_root)
        if not self._pdf_choices:
            return SessionReply("Nenhum PDF foi encontrado na pasta atual.")
        self._awaiting_pdf_choice = True
        lines = ["PDFs encontrados:"]
        lines.extend(f"{index}. {path.name}" for index, path in enumerate(self._pdf_choices, 1))
        lines.append("Digite apenas o número do PDF.")
        return SessionReply("\n".join(lines))

    def _select_pdf(self, text: str) -> SessionReply:
        try:
            number = int(text)
        except ValueError:
            return SessionReply("Escolha um PDF digitando apenas o número da lista.")
        if number < 1 or number > len(self._pdf_choices):
            return SessionReply("Número inválido. Escolha um item da lista.")
        self._awaiting_pdf_choice = False
        selected = self._pdf_choices[number - 1]
        evidence = self.pdf_extractor.extract(selected)
        self._contract = UmlExtractor().extract(evidence)
        self._store.close()
        self._store = ProjectStore.open(
            pdf_sha256(selected), project_identifier(self.config.project_root), self.config.state_dir
        )
        self._store.remember("pdf", f"Selecionado: {selected.name}; fonte: {evidence.source}")
        self.evidence.confirmed_pdf.append(f"Arquivo selecionado: {selected.name}")
        self.evidence.confirmed_pdf.append(f"Extração utilizada: {evidence.source}")
        for java_class in self._contract.classes:
            self.evidence.inferred_uml.append(f"Classe {java_class.name}")
        self._ambiguities = [
            index
            for index, relationship in enumerate(self._contract.relationships)
            if relationship.confidence < 0.9 and relationship.alternatives
        ]
        summary = ", ".join(item.name for item in self._contract.classes) or "nenhuma classe segura"
        if self._ambiguities:
            return SessionReply(
                f"PDF carregado. Classes reconhecidas: {summary}.\n" + self._ambiguity_question()
            )
        return SessionReply(f"PDF carregado. Classes reconhecidas: {summary}.")

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
        return SessionReply(f"Interpretação registrada: {selected}. Agora posso gerar o código.")

    @staticmethod
    def _text_arg(action: Action, name: str) -> str:
        value = action.args.get(name)
        if not isinstance(value, str):
            raise ValueError(f"Argumento textual obrigatório: {name}")
        return value

    def _execute_action(self, action: Action) -> str:
        if action.tool == "read_file":
            path = self._text_arg(action, "path")
            return self.workspace.read(Path(path))
        if action.tool == "write_file":
            path = self._text_arg(action, "path")
            content = self._text_arg(action, "content")
            change = self.workspace.write(Path(path), content)
            self.history.record(change)
            self._store.remember("change", f"Arquivo escrito: {path}")
            return f"Arquivo salvo: {path}"
        if action.tool == "apply_patch":
            path = self._text_arg(action, "path")
            change = self.workspace.apply_patch(
                Path(path),
                self._text_arg(action, "expected"),
                self._text_arg(action, "replacement"),
            )
            self.history.record(change)
            self._store.remember("change", f"Arquivo ajustado: {path}")
            return f"Arquivo ajustado: {path}"
        if action.tool == "compile_java":
            raw_sources = action.args.get("sources")
            if raw_sources is None:
                sources = [path.relative_to(self.config.project_root) for path in self.config.project_root.rglob("*.java")]
            elif isinstance(raw_sources, list) and all(isinstance(item, str) for item in raw_sources):
                sources = [Path(item) for item in raw_sources]
            else:
                raise ValueError("sources precisa ser uma lista de caminhos.")
            result = self.toolchain.compile(sources)
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
            timeout_s = max(1, min(15, int(requested_timeout)))
            result = self.toolchain.run(main_class, timeout_s)
            if result.success:
                self.evidence.locally_tested.append(f"{main_class}: execução concluída")
                return f"Execução concluída. Saída:\n{result.stdout}"
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

    def _chat(self, text: str) -> SessionReply:
        messages = build_context(
            criteria=load_criteria(self.config),
            contract=self._contract_text(),
            memory_summary=self._store.summary(),
            relevant_files=self._relevant_files(),
            user_request=text,
        )
        messages[0] = Message("system", messages[0].content + "\n\n" + _ACTION_PROTOCOL)
        actions_used = 0
        while True:
            reply = self.model.complete(messages)
            try:
                action = parse_action(reply.content)
            except ActionValidationError:
                self._store.remember("assistant", reply.content)
                return SessionReply(reply.content)
            if actions_used >= 3:
                return SessionReply(
                    "Parei após três ações automáticas para evitar alterações repetitivas. "
                    "Revise o estado e peça para continuar."
                )
            actions_used += 1
            try:
                result = self._execute_action(action)
            except (OSError, ValueError, PatchMismatchError, RuntimeError) as exc:
                result = f"AÇÃO RECUSADA OU FALHOU: {exc}"
            messages.append(Message("assistant", reply.content))
            messages.append(Message("user", f"RESULTADO DA AÇÃO:\n{result}"))

    def handle(self, text: str) -> SessionReply:
        stripped = text.strip()
        if not stripped:
            return SessionReply("")
        lowered = stripped.casefold()
        if lowered in {"/sair", "sair"}:
            return SessionReply("Até logo.", True)
        if lowered == "/pdf":
            return self._list_pdfs()
        if lowered == "/desfazer":
            return SessionReply(self.history.undo_last().reason)
        if lowered == "/relatorio":
            return SessionReply(self.evidence.render())
        if lowered == "/ajuda":
            return SessionReply("Comandos: /pdf, /desfazer, /relatorio, /ajuda e /sair.")
        if self._awaiting_pdf_choice:
            return self._select_pdf(stripped)
        if self._ambiguities:
            if not stripped.isdigit():
                return SessionReply("Antes de gerar, escolha uma interpretação.\n" + self._ambiguity_question())
            return self._resolve_ambiguity(stripped)
        return self._chat(stripped)
