"""Hybrid state machine joining chat, PDF evidence and safe local tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Protocol
import unicodedata

from .config import AppConfig
from .criteria import build_context, ensure_criteria, load_criteria
from .java.toolchain import JavaToolchain
from .java.judge import Judge
from .java.validator import ContractValidator
from .java.methods import locate_methods, extract_body, validate_method
from .memory.project import ProjectMemory
from .memory.store import pdf_sha256, text_sha256
from .model.actions import Action, ActionValidationError, parse_action
from .model.client import Message, ModelReply
from .pdf.discovery import discover_pdfs
from .pdf.extract import PdfEvidence, PdfExtractor
from .review.report import EvidenceReport
from .uml.extract import UmlExtractor
from .uml.models import JavaContract, Relationship
from .workspace.files import PatchMismatchError, Workspace
from .workspace.history import History


class ModelLike(Protocol):
    def complete(self, messages: list[Message], *, max_tokens: int | None = None) -> ModelReply: ...


def _fold_text(text: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(character)
    )


def _diagnostic_guidance(diagnostic: str) -> str:
    normalized = diagnostic.casefold()
    guidance: list[str] = []
    if "int cannot be converted to double" in normalized:
        guidance.append(
            "Para atribuir um int a Double em Java 8, converta antes para double, "
            "por exemplo: Double valor = (double) inteiro;"
        )
    return "\n".join(guidance)


def _failure_owner(failures: tuple[str, ...] | list[str], names: list[str]) -> str | None:
    for failure in failures:
        owner = failure.split(".", 1)[0]
        if owner in names:
            return owner
    for failure in failures:
        match = re.search(r"(?:Classe ausente: |Campo ausente ou divergente: |Método ausente ou divergente: |Herança ausente: )([\w$À-ÿ]+)", failure)
        if match and match.group(1) in names:
            return match.group(1)
        match = re.search(r"([^:\n/\\]+)\.java:\d+:\s*error", failure)
        if match and match.group(1) in names:
            return match.group(1)
    return None


def _extract_java_source(text: str, class_name: str) -> str:
    candidate = text.strip()
    write_start = re.search(
        rf'<write_file path="{re.escape(class_name)}\.java">\s*', candidate
    )
    if write_start:
        closing = candidate.find("</write_file>", write_start.end())
        if closing < 0:
            raise ValueError("O bloco de arquivo retornado ficou incompleto.")
        candidate = candidate[write_start.end():closing].strip()
    elif candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("O bloco de código retornado ficou incompleto.")
        candidate = "\n".join(lines[1:-1]).strip()

    public_classes = re.findall(
        r"\bpublic\s+(?:abstract\s+|final\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)",
        candidate,
    )
    if public_classes != [class_name]:
        raise ValueError(
            f"Era esperada somente a classe pública {class_name}, mas vieram: "
            + (", ".join(public_classes) or "nenhuma")
        )
    if "<write_file" in candidate or "<compile_java" in candidate:
        raise ValueError("A resposta misturou ações com o código Java.")
    return candidate.rstrip() + "\n"


def _required_generation_rules(requirements: str) -> tuple[str, ...]:
    normalized = _fold_text(requirements)
    rules: list[str] = []
    for match in re.finditer(
        r"\b(aumenta|aumento|reduzid[ao]|reducao)\s+(?:em|de)\s+(\d+(?:[.,]\d+)?)\s*%",
        normalized,
    ):
        kind, percentage = match.groups()
        fraction = Decimal(percentage.replace(",", ".")) / 100
        factor = 1 + fraction if kind.startswith("aument") else 1 - fraction
        literal = format(factor, ".1f") if factor == factor.to_integral_value() else str(factor)
        rules.append(f"{match.group(0)}: resultado = base * {literal}")
    for pattern, factor in (
        (r"\b(?:reduzid[ao]|reducao)\s+(?:pela|a)\s+metade\b", "0.5"),
        (r"\b(?:reduzid[ao]|reducao)\s+em\s+um\s+quarto\b", "0.75"),
    ):
        if re.search(pattern, normalized):
            rules.append(f"redução fracionária: resultado = base * {factor}")
    if re.search(r"nunca[^.\n]*maior\s+que", normalized):
        rules.append(
            "invariante 'nunca pode ser maior': valide explicitamente no construtor "
            "e lance IllegalArgumentException se o valor exceder o limite"
        )
    return tuple(dict.fromkeys(rules))


def _semantic_issues(requirements: str, source: str) -> tuple[str, ...]:
    normalized = _fold_text(requirements)
    compact_source = source.casefold()
    issues: list[str] = []

    if re.search(r"nunca[^.\n]*maior\s+que", normalized):
        has_upper_bound_guard = ">" in compact_source and any(
            marker in compact_source
            for marker in ("throw ", "math.min(", "?", "return")
        )
        if not has_upper_bound_guard:
            issues.append(
                "A regra 'nunca pode ser maior' exige validação explícita do limite, "
                "por exemplo lançando IllegalArgumentException quando o valor exceder a capacidade."
            )

    return tuple(issues)


@dataclass(frozen=True)
class SessionReply:
    text: str
    exit_requested: bool = False


_ACTION_PROTOCOL = """
Responda SEMPRE com exatamente um dos blocos abaixo, sem crases e sem texto externo.
Para escrever uma classe, use código Java direto, sem aspas e sem concatenação:
<write_file path="Classe.java">
public class Classe {
}
</write_file>
Para compilar: <compile_java />
Para executar: <run_java main_class="Main" />
Para encerrar: <respond>mensagem final em português</respond>
Para read_file, apply_patch e memory, o formato JSON anterior continua aceito.
Nunca use shell. Use exatamente uma ferramenta por resposta.

REGRAS CRÍTICAS PARA JAVA:
- Em write_file, grave exatamente UM arquivo .java por ação.
- O conteúdo deve ter no máximo UMA classe public e ela deve ter o mesmo nome do arquivo.
- Não use package, getters, setters, equals, hashCode ou toString, exceto se o enunciado pedir.
- Implemente somente atributos, construtores e métodos pedidos, com a visibilidade exata do UML.
- Se forem necessários vários arquivos, grave apenas um agora; após o resultado, grave o próximo.
- Seja compacto para a resposta não ser cortada.
- Depois de criar todos os arquivos, obrigatoriamente use compile_java e corrija qualquer erro.
- Quando houver classe main, use run_java antes de respond.
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
        self.evidence = EvidenceReport()
        self._criteria_path = ensure_criteria(config, criteria_template)
        self._pdf_choices: list[Path] = []
        self._awaiting_pdf_choice = False
        self._awaiting_enunciado = False
        self._enunciado_lines: list[str] = []
        self._contract: JavaContract | None = None
        self._enunciado_invalid = False
        self._pdf_text = ""
        self._ambiguities: list[int] = []
        self._closed = False
        self.memory = ProjectMemory.open(config.project_root, config.state_dir)
        self._store = self.memory
        self.resume_message = "Novo projeto iniciado nesta pasta. Use /pdf ou /enunciado."
        try:
            self.history = History(self.workspace, recovery=self.memory.files)
            self.memory.import_legacy(self.memory.manifest.pdf_hash)
            requirements = self.memory.requirements
            if requirements:
                valid = requirements.identity == self.memory.manifest.pdf_hash
                warning = "Memória de requisitos inconsistente; selecione o enunciado novamente."
                pdf_path = self.memory.manifest.pdf_path
                if pdf_path:
                    try:
                        path = self.workspace._resolve(Path(pdf_path))
                        valid = valid and pdf_sha256(path) == self.memory.manifest.pdf_hash
                    except OSError:
                        valid = False
                    warning = "PDF mudou ou ficou indisponível; use /pdf para reler."
                if valid:
                    self._contract = requirements.contract if requirements.contract.classes else None
                    self._enunciado_invalid = not requirements.contract.classes
                    self._pdf_text = requirements.text[:12_000]
                    self._ambiguities = [index for index, item in enumerate(requirements.contract.relationships)
                                         if item.confidence < .9 and item.alternatives]
                    self.memory.update_criteria(load_criteria(config))
                    snapshot = self.memory.load_verifications()
                    self.evidence.confirmed_pdf.append(f"Enunciado retomado: {pdf_path or 'texto colado'}")
                    self.evidence.inferred_uml.extend(f"Classe {item.name}" for item in requirements.contract.classes)
                    if self.memory.has_valid_compilation():
                        self.evidence.compiled.extend(snapshot.source_hashes)
                        self.evidence.locally_tested.extend(snapshot.locally_tested)
                    self.evidence.unproven.extend(snapshot.unproven)
                    self.resume_message = "Projeto retomado. " + self.memory.next_action() + "\n" + self._render_contract()
                else:
                    self._enunciado_invalid = True
                    self.memory.invalidate(warning)
                    self.resume_message = "Projeto retomado. " + warning
        except BaseException:
            self.memory.close()
            raise

    def close(self) -> None:
        if not self._closed:
            try:
                self._store.close()
            finally:
                self.toolchain.close()
                self._closed = True

    def _contract_text(self) -> str:
        if self._contract is None:
            return ""
        return json.dumps(
            asdict(self._contract), ensure_ascii=False, separators=(",", ":")
        )

    def _render_contract(self) -> str:
        if self._contract is None:
            return "Nenhum contrato carregado. Use /enunciado ou /pdf."
        lines = ["Contrato interpretado do enunciado (não é validação do código):"]
        for java_class in self._contract.classes:
            parents = [
                item.parent for item in self._contract.relationships
                if item.child == java_class.name and item.kind == "inheritance"
            ]
            header = java_class.name
            if parents:
                header += " extends " + ", ".join(parents)
            lines.append(header)
            for field in java_class.fields:
                lines.append(f"  {field.visibility} {field.name}: {field.type_name}")
            for method in java_class.methods:
                parameters = ", ".join(f"{name}: {kind}" for name, kind in method.parameters)
                signature = f"  {method.visibility} {method.name}({parameters})"
                if method.name != java_class.name:
                    signature += f": {method.type_name}"
                lines.append(signature)
        for item in self._contract.relationships:
            lines.append(
                f"Relacionamento: {item.parent} → {item.child}: {item.kind} "
                f"(confiança {item.confidence:.0%})"
            )
        lines.append("Incertezas:")
        lines.extend(f"- {warning}" for warning in self._contract.warnings)
        if not self._contract.warnings:
            lines.append("- Nenhuma sinalizada pelo extrator; interpretação ainda sujeita a revisão.")
        return "\n".join(lines)

    def _relevant_files(self) -> dict[str, str]:
        selected: dict[str, str] = {}
        remaining = 6_000
        for path in sorted(self.config.project_root.rglob("*.java")):
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
        while self._contract:
            relationship = next(
                (item for item in self._contract.relationships if item.child == current),
                None,
            )
            if relationship is None:
                break
            needed.add(f"{relationship.parent}.java")
            current = relationship.parent
        return {
            path: content
            for path, content in all_files.items()
            if Path(path).name in needed
        }

    def _required_java_names(self) -> list[str]:
        names = [item.name for item in self._contract.classes] if self._contract else []
        for match in re.finditer(
            r"\bclasse\s*:?[ \t]+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*main\s*\)",
            self._pdf_text,
            flags=re.IGNORECASE,
        ):
            names.append(match.group(1))
        return list(dict.fromkeys(names))

    def _main_class_name(self) -> str | None:
        match = re.search(
            r"\bclasse\s*:?[ \t]+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*main\s*\)",
            self._pdf_text,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1)
        if self._contract is not None:
            for java_class in self._contract.classes:
                if any(method.name == "main" for method in java_class.methods):
                    return java_class.name
        if "Main" in self._required_java_names():
            return "Main"
        return None

    def _missing_java_names(self) -> list[str]:
        return [
            name
            for name in self._required_java_names()
            if not (self.config.project_root / f"{name}.java").is_file()
        ]

    def _focused_requirements(self, name: str) -> str:
        parts: list[str] = []
        parent: str | None = None
        focused_rules = ""
        if self._contract:
            for java_class in self._contract.classes:
                if java_class.name == name:
                    parts.append(
                        "UML DA CLASSE: "
                        + json.dumps(asdict(java_class), ensure_ascii=False, separators=(",", ":"))
                    )
                    declarations = [
                        f"{field.visibility} {field.type_name} {field.name};"
                        for field in java_class.fields
                    ]
                    for method in java_class.methods:
                        parameters = ", ".join(
                            f"{type_name} {parameter_name}"
                            for parameter_name, type_name in method.parameters
                        )
                        if method.name == java_class.name:
                            declarations.append(
                                f"{method.visibility} {java_class.name}({parameters});"
                            )
                        else:
                            declarations.append(
                                f"{method.visibility} {method.type_name} "
                                f"{method.name}({parameters});"
                            )
                    parts.append(
                        "DECLARAÇÕES JAVA OBRIGATÓRIAS (copie tipos e visibilidades "
                        "literalmente):\n" + "\n".join(declarations)
                    )
            relationships = [
                asdict(item)
                for item in self._contract.relationships
                if item.child == name or item.parent == name
            ]
            if relationships:
                parts.append(
                    "RELACIONAMENTOS: "
                    + json.dumps(relationships, ensure_ascii=False, separators=(",", ":"))
                )
            parent = next(
                (
                    item.parent
                    for item in self._contract.relationships
                    if item.child == name
                    and item.kind == "inheritance"
                    and item.confidence >= 0.9
                ),
                None,
            )
            if parent:
                parts.append(f"CABEÇALHO OBRIGATÓRIO: public class {name} extends {parent}")

        lines = self._pdf_text.splitlines()
        class_names = {_fold_text(item) for item in self._required_java_names()}
        target = _fold_text(name)
        def heading(line):
            match = re.fullmatch(
                r"(?:#{1,6}\s*)?(?:(?:class|classe)\s*:?\s*)?([\w$À-ÿ]+)(?:\s*:\s*(?:\(.*\))?)?",
                line.strip(), flags=re.I,
            )
            return _fold_text(match.group(1)) if match else ""
        starts = [
            index
            for index, line in enumerate(lines)
            if heading(line) == target
        ]
        if starts:
            start = starts[-1]
            end = len(lines)
            for index in range(start + 1, len(lines)):
                next_heading = heading(lines[index])
                if next_heading in class_names or _fold_text(lines[index].strip()).startswith("instrucao final"):
                    end = index
                    break
            focused_rules = "\n".join(lines[start:end]).strip()
            parts.append("REGRAS ESPECÍFICAS DO PDF:\n" + focused_rules)
        elif name == self._main_class_name():
            final_starts = [
                index
                for index, line in enumerate(lines)
                if _fold_text(line.strip()).startswith("instrucao final")
            ]
            if final_starts:
                focused_rules = "\n".join(lines[final_starts[-1]:]).strip()
            else:
                focused_rules = "\n".join(
                    line for line in lines if f"{target} (main)" in _fold_text(line)
                ).strip()
            if focused_rules:
                parts.append("REGRAS ESPECÍFICAS DO PDF:\n" + focused_rules)
        elif self._pdf_text:
            focused_rules = self._pdf_text
            parts.append("TEXTO DO PDF PARA ESTA CLASSE:\n" + focused_rules)

        arithmetic = _required_generation_rules(focused_rules)
        if arithmetic:
            parts.append("FATOS ARITMÉTICOS OBRIGATÓRIOS:\n" + "\n".join(arithmetic))
        parts.append(
            "VERIFICAÇÃO GERAL: aumento de X% = base * (1 + X/100); redução de X% = "
            "base * (1 - X/100). Não aplique duas vezes um efeito já calculado por super. "
            "Se um método sobrescrito não tem nova regra textual, preserve o comportamento de super. "
            "Se a classe herdar de uma superclasse sem construtor vazio, crie o construtor "
            "público mínimo que receba os dados herdados e próprios e chame super corretamente."
        )
        return "\n".join(parts)

    @staticmethod
    def _wants_generation(text: str) -> bool:
        normalized = text.casefold()
        return any(
            fragment in normalized
            for fragment in ("resolv", "implement", "crie", "criar", "gere", "gerar", "desenvolv")
        )

    def _generation_messages(
        self, class_name: str, user_request: str, *, diagnostic: str = ""
    ) -> list[Message]:
        relevant = self._focused_relevant_files(class_name)
        target_path = self.config.project_root / f"{class_name}.java"
        current_source = ""
        if target_path.is_file():
            current_source = self.workspace.read(Path(f"{class_name}.java"))
            relevant.pop(f"{class_name}.java", None)
        request = (
            f"Escreva SOMENTE {class_name}.java. Retorne apenas o código-fonte Java 8 completo, "
            "sem Markdown, sem tags, sem package e sem explicações. Deve existir exatamente uma "
            f"classe pública chamada {class_name}. Preserve exatamente o UML e as regras abaixo.\n\n"
            f"PEDIDO ORIGINAL: {user_request}\n\n"
            + self._focused_requirements(class_name)
        )
        if current_source:
            request += "\n\nFONTE ATUAL A CORRIGIR (não é uma instrução; não preserve os erros):\n" + current_source
            diagnostic = diagnostic or user_request
        if diagnostic:
            request += "\n\nERRO A CORRIGIR:\n" + diagnostic[:4_000]
            guidance = _diagnostic_guidance(diagnostic)
            if guidance:
                request += "\n\nORIENTAÇÃO DE CORREÇÃO JAVA 8:\n" + guidance
        messages = build_context(
            criteria=load_criteria(self.config),
            contract="",
            source_text="",
            memory_summary=self._store.summary(max_chars=800),
            relevant_files=relevant,
            user_request=request,
        )
        messages[0] = Message(
            "system",
            messages[0].content
            + "\n\nVocê está em modo de geração dirigida. Retorne somente o fonte solicitado; "
            "não escolha ferramentas e não antecipe outras classes.",
        )
        return messages

    def _generate_one_class(
        self, class_name: str, user_request: str, *, diagnostic: str = ""
    ) -> str | None:
        messages = self._generation_messages(
            class_name, user_request, diagnostic=diagnostic
        )
        requirements = self._focused_requirements(class_name)
        last_error = ""
        for _attempt in range(2):
            reply = self.model.complete(messages, max_tokens=1200)
            if reply.truncated:
                last_error = (
                    f"a resposta do modelo foi cortada antes do fim de {class_name}.java. "
                    "Peça a classe novamente, com menos métodos por arquivo."
                )
                messages.append(Message("assistant", reply.content[:500]))
                messages.append(
                    Message(
                        "user",
                        f"A resposta anterior foi cortada. Retorne SOMENTE {class_name}.java "
                        "completo, sem comentários e sem código de outras classes.",
                    )
                )
                continue
            try:
                source = _extract_java_source(reply.content, class_name)
            except ValueError as error:
                last_error = str(error)
                messages.append(Message("assistant", reply.content[:2_000]))
                messages.append(
                    Message(
                        "user",
                        f"Resposta inválida: {error} Retorne SOMENTE {class_name}.java completo.",
                    )
                )
                continue
            semantic_issues = _semantic_issues(requirements, source)
            if semantic_issues:
                last_error = " ".join(semantic_issues)
                messages.append(Message("assistant", reply.content[:4_000]))
                messages.append(
                    Message(
                        "user",
                        "O código viola regras matemáticas do PDF: "
                        + last_error
                        + f" Retorne SOMENTE {class_name}.java completo e corrigido.",
                    )
                )
                continue
            self.history.write(Path(f"{class_name}.java"), source)
            self.evidence.compiled.clear()
            self.evidence.locally_tested.clear()
            self._store.remember("change", f"Arquivo escrito: {class_name}.java")
            return None
        return last_error or "O modelo não retornou uma classe Java válida."

    def _correct_methods(self, class_name: str, request: str, diagnostic: str = "") -> str | None:
        relative = Path(f"{class_name}.java")
        found = locate_methods(self.toolchain, relative, class_name)
        explicit = re.search(
            rf"(?:\b{re.escape(class_name)}\.|"
            r"(?i:\b(?:corrij\w*|ajust\w*|alter\w*|modifi\w*)\s+(?:(?:somente|apenas)\s+)?(?:o\s+)?m[eé]todo\s+))"
            r"([\w$]+)(?:\s*\(([^)]*)\))?",
            request,
        )
        if not explicit:
            explicit = re.search(
                rf"(?i:\b(?:somente|apenas)\s+(?:o\s+)?)([\w$]+)(?:\s*\(([^)]*)\))?"
                rf"(?i:\s+(?:de|da)\s+){re.escape(class_name)}\b", request)
        selected = list(found)
        if explicit:
            selected = [item for item in found if item.name == explicit.group(1)]
            if explicit.group(2) is not None:
                types = tuple(part.strip() for part in explicit.group(2).split(",") if part.strip())
                selected = [item for item in selected if item.parameter_types == types]
            if len(selected) != 1:
                return "Identifique a sobrecarga pela assinatura: " + "; ".join(item.signature for item in found)
        elif re.search(r"\b(?:somente|apenas|s[oó])\b", request, re.I) and not re.search(
                rf"(?i:\b(?:somente|apenas|s[oó])\s+(?:a\s+classe\s+)?){re.escape(class_name)}\b", request):
            return f"Identifique o método restrito como {class_name}.metodo(tipos). Nenhum corpo foi alterado."
        if not selected:
            return "Nenhum corpo de método disponível; construtores e assinaturas foram preservados."
        identities = [(item.name, item.parameter_types) for item in selected]
        for name, types in identities:
            source = self.workspace.read(relative)
            current = locate_methods(self.toolchain, relative, class_name)
            method = next(item for item in current if (item.name, item.parameter_types) == (name, types))
            structure = source
            for item in reversed(current):
                structure = structure[:item.start] + "{ /* corpo omitido */ }" + structure[item.end:]
            relevant = self._focused_relevant_files(class_name)
            relevant.pop(str(relative), None)
            prompt = (
                f"Corrija somente o corpo do método de {class_name} com assinatura {method.signature}. "
                "Retorne somente o bloco Java entre { e }, sem assinatura, classe, Markdown ou explicações. "
                "Não altere atributos, construtores ou outros métodos.\n\n"
                + self._focused_requirements(class_name)
                + "\n\nESTRUTURA ATUAL (corpos omitidos):\n" + structure
                + "\n\nCORPO ATUAL COM ERRO:\n" + source[method.start:method.end]
                + "\n\nPEDIDO DE CORREÇÃO:\n" + request
                + "\n\nDIAGNÓSTICO:\n" + (diagnostic or request)[:4000]
                + f"\n\nNESTA CHAMADA: somente {method.signature}. "
                "Retorne somente o corpo entre { e }, sem assinatura ou outros métodos."
            )
            messages = build_context(criteria=load_criteria(self.config), contract="", source_text="",
                memory_summary="", relevant_files=relevant, user_request=prompt)
            messages[0] = Message("system", messages[0].content
                + "\n\nMODO: CORREÇÃO DE UM CORPO. Responda somente com um bloco Java que começa com { e termina com }. "
                "Não retorne assinaturas, classes, Markdown nem outros métodos. O pedido completo serve de contexto; "
                f"nesta chamada altere somente o corpo de {method.signature} na classe {class_name}.")
            last_error = ""
            for _attempt in range(2):
                reply = self.model.complete(messages, max_tokens=500)
                try:
                    if reply.truncated:
                        raise ValueError("Resposta cortada; retorne somente o corpo completo.")
                    body = extract_body(reply.content)
                    candidate = validate_method(self.workspace, self.toolchain, self._contract,
                                                relative, method, body, source)
                    if candidate != source:
                        self.history.write(relative, candidate, expected=source)
                        self.evidence.compiled.clear()
                        self.evidence.locally_tested.clear()
                        self._store.remember("change", f"Corpo corrigido: {class_name}.{name}({', '.join(types)})")
                    break
                except PatchMismatchError:
                    raise
                except ValueError as error:
                    last_error = str(error)
                    messages.append(Message("assistant", reply.content[:2000]))
                    messages.append(Message("user", last_error + " Retorne somente o corpo Java corrigido."))
            else:
                return last_error
        return None

    def _guided_solve(self, text: str, target: str | None = None) -> SessionReply:
        created: list[str] = []
        for class_name in ([target] if target else self._missing_java_names()):
            if target and (self.config.project_root / f"{class_name}.java").is_file():
                error = self._correct_methods(class_name, text)
            else:
                error = self._generate_one_class(class_name, text)
            if error:
                return SessionReply(
                    f"Parei ao gerar {class_name}.java: {error} Os arquivos anteriores foram preservados."
                )
            created.append(f"{class_name}.java")

        sources = [
            path.relative_to(self.config.project_root)
            for path in self.config.project_root.rglob("*.java")
        ]
        compilation = self.toolchain.compile(sources)
        self.memory.record_verification(compilation.success, diagnostics=compilation.diagnostics)
        repairs = 0
        while not compilation.success and repairs < 2:
            match = re.search(r"(?m)([^:\n]+\.java):\d+:\s*error", compilation.diagnostics)
            if not match:
                break
            class_name = Path(match.group(1)).stem
            if target and class_name != target:
                break
            if not (self.config.project_root / f"{class_name}.java").is_file():
                break
            if target:
                error = self._correct_methods(class_name, text, compilation.diagnostics)
            else:
                error = self._generate_one_class(class_name, text, diagnostic=compilation.diagnostics)
            if error:
                break
            repairs += 1
            compilation = self.toolchain.compile(sources)
            self.memory.record_verification(compilation.success, diagnostics=compilation.diagnostics)

        if not compilation.success:
            self._store.remember("compile", f"Falha: {compilation.diagnostics[:1000]}")
            return SessionReply(
                "Os arquivos foram criados, mas a compilação ainda falhou após correções automáticas:\n"
                + compilation.diagnostics
            )

        if self._contract is not None:
            validator = ContractValidator(self.toolchain)
            validation = validator.validate(self._contract, self.config.project_root)
            structural_repairs = 0
            repair_limit = max(2, len(self._contract.classes))
            while not validation.valid and structural_repairs < repair_limit:
                self.memory.record_verification(validation.compilation.success, diagnostics="\n".join(validation.issues))
                diagnostic = "\n".join(validation.issues)
                class_name = _failure_owner(validation.issues, [item.name for item in self._contract.classes])
                if class_name is None:
                    break
                if target and class_name != target:
                    break
                if target:
                    break  # Body-only corrections cannot repair missing members or signatures.
                error = self._generate_one_class(
                    class_name,
                    text,
                    diagnostic="DIVERGÊNCIA COM O UML:\n" + diagnostic,
                )
                if error:
                    break
                structural_repairs += 1
                validation = validator.validate(self._contract, self.config.project_root)
            if not validation.valid:
                issues = "\n".join(validation.issues)
                self._store.remember("validation", f"Falha: {issues[:1000]}")
                self.memory.record_verification(validation.compilation.success, diagnostics=issues)
                return SessionReply(
                    "As classes compilam, mas ainda divergem do UML após correções automáticas:\n"
                    + issues
                )
            compilation = validation.compilation

        names = ", ".join(str(item) for item in sources)
        self.evidence.compiled.append(names)
        self._store.remember("compile", f"Sucesso: {names}")
        if self._contract is not None:
            judge = Judge(self.toolchain, self.model)
            cases = judge.build_cases(self._contract, self._pdf_text)
            report = judge.run(cases)
            for _attempt in range(2):
                if not report.failed:
                    break
                diagnostic = "\n".join(report.failed)
                class_name = _failure_owner(report.failed, [item.name for item in self._contract.classes])
                if class_name is None or (target and class_name != target):
                    break
                if self._correct_methods(class_name, text, diagnostic=diagnostic):
                    break
                report = judge.run(cases)
            self.evidence.locally_tested = list(report.passed)
            self.evidence.unproven = list(report.unverified)
            self._store.remember("judge", json.dumps(asdict(report), ensure_ascii=False))
            if report.failed:
                self.evidence.unproven.extend(report.failed)
                final_validation = ContractValidator(self.toolchain).validate(self._contract, self.config.project_root)
                self.memory.record_verification(final_validation.compilation.success, structural=final_validation.valid,
                    locally_tested=report.passed, unproven=self.evidence.unproven, diagnostics="\n".join(report.failed))
                self.evidence.compiled = [names] if final_validation.compilation.success else []
                return SessionReply(
                    "As verificações locais ainda falharam após tentativas limitadas:\n"
                    + "\n".join(report.failed + report.unverified)
                )
        self.evidence.compiled = [names]
        self.memory.record_verification(True, structural=self._contract is not None,
            locally_tested=self.evidence.locally_tested, unproven=self.evidence.unproven,
            diagnostics="Compilação Java 8 e verificações locais registradas; cobertura completa não comprovada.")
        main_class = self._main_class_name()
        run_summary = ""
        if main_class:
            execution = self.toolchain.run(main_class, 15)
            if execution.success:
                run_summary = f" e {main_class} foi executada"
            else:
                return SessionReply(
                    f"As classes compilaram, mas {main_class} falhou na execução:\n"
                    + (execution.stderr or execution.stdout)
                )
        created_text = ", ".join(created) if created else "arquivos existentes"
        return SessionReply(
            f"Arquivos preparados: {created_text}; compilação Java 8 aprovada{run_summary}.\n"
            f"Casos locais inferidos aprovados: {len(self.evidence.locally_tested)}. "
            "Cobertura completa e avaliação dos jurados não comprovadas."
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
        return self._apply_evidence(evidence, pdf_sha256(selected), selected.name)

    def _finish_enunciado(self) -> SessionReply:
        raw = "\n".join(self._enunciado_lines)
        self._awaiting_enunciado = False
        self._enunciado_lines = []
        if not raw.strip():
            return SessionReply("Nenhum texto recebido. Use /enunciado novamente.")
        evidence = PdfEvidence(text=raw, source="texto colado", warnings=())
        return self._apply_evidence(evidence, "texto-" + text_sha256(raw), "texto colado")

    def _apply_evidence(
        self, evidence: PdfEvidence, identity: str, label: str
    ) -> SessionReply:
        contract = UmlExtractor().extract(evidence)
        self.memory.select_requirements(contract, evidence.text, evidence.source, identity,
                                        label if label.lower().endswith(".pdf") else None,
                                        load_criteria(self.config))
        self.memory.import_legacy(identity)
        self.evidence = EvidenceReport()
        if not contract.classes:
            self._enunciado_invalid = True
            self._contract = None
            self._pdf_text = ""
            self._ambiguities = []
            return SessionReply(
                "Não reconheci nenhuma classe no enunciado. Envie o diagrama com as classes, "
                "os atributos e os métodos, ou corrija o texto e use /enunciado novamente."
            )
        self._contract = contract
        self._enunciado_invalid = False
        self._pdf_text = evidence.text[:12_000]
        self._store.remember("pdf", f"Selecionado: {label}; fonte: {evidence.source}")
        self.evidence.confirmed_pdf.append(f"Enunciado: {label}")
        self.evidence.confirmed_pdf.append(f"Extração utilizada: {evidence.source}")
        for java_class in self._contract.classes:
            self.evidence.inferred_uml.append(f"Classe {java_class.name}")
        self._ambiguities = [
            index
            for index, relationship in enumerate(self._contract.relationships)
            if relationship.confidence < 0.9 and relationship.alternatives
        ]
        summary = ", ".join(item.name for item in self._contract.classes)
        if self._ambiguities:
            return SessionReply(
                f"Enunciado carregado. Classes reconhecidas: {summary}.\n"
                + self._ambiguity_question()
            )
        return SessionReply(f"Enunciado carregado. Classes reconhecidas: {summary}.")

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
        self.memory.select_requirements(self._contract, self.memory.requirements.text,
            self.memory.requirements.source, self.memory.requirements.identity,
            self.memory.manifest.pdf_path, load_criteria(self.config))
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
        if action.tool in {"read_file", "write_file", "apply_patch"}:
            relative = self.workspace._resolve(Path(self._text_arg(action, "path"))).relative_to(self.config.project_root)
            if ".assistente" in relative.parts:
                raise ValueError("A memória canônica é gerida somente pelo controlador.")
        if action.tool == "read_file":
            path = self._text_arg(action, "path")
            return self.workspace.read(Path(path))
        if action.tool == "write_file":
            path = self._text_arg(action, "path")
            content = self._text_arg(action, "content")
            self.history.write(Path(path), content)
            self.evidence.compiled.clear()
            self.evidence.locally_tested.clear()
            self._store.remember("change", f"Arquivo escrito: {path}")
            return f"Arquivo salvo: {path}"
        if action.tool == "apply_patch":
            path = self._text_arg(action, "path")
            expected = self._text_arg(action, "expected")
            if self.workspace.read(Path(path)) != expected:
                raise PatchMismatchError("O arquivo mudou ou o trecho esperado não corresponde exatamente.")
            self.history.write(Path(path), self._text_arg(action, "replacement"))
            self.evidence.compiled.clear()
            self.evidence.locally_tested.clear()
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
            self.memory.record_verification(result.success, diagnostics=result.diagnostics, sources=sources)
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
        if self._enunciado_invalid:
            return SessionReply("Enunciado sem contrato válido. Use /pdf para reler ou /enunciado para informar o diagrama.")
        if self._contract is not None and not self._contract.classes:
            return SessionReply(
                "\n".join(self._contract.warnings)
                + "\nEnvie o diagrama com as classes antes de gerar código."
            )
        if self._contract is not None and re.search(r"\b(?:corrij\w*|ajust\w*|alter\w*|modifi\w*)", text, re.I):
            targets = [item.name for item in self._contract.classes
                       if re.search(rf"(?<!\w){re.escape(item.name)}(?!\w)", text, re.I)]
            if len(targets) == 1:
                return self._guided_solve(text, target=targets[0])
            if targets:
                return SessionReply("Indique uma classe por pedido de correção para preservar as demais.")
        initial_missing = self._missing_java_names()
        if self._contract is not None and self._wants_generation(text):
            return self._guided_solve(text)
        focused_target = initial_missing[0] if initial_missing else None
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
        )
        messages[0] = Message("system", messages[0].content + "\n\n" + _ACTION_PROTOCOL)
        actions_used = 0
        consecutive_failures = 0
        wrote_in_request = False
        compiled_in_request = False
        ran_in_request = False
        compile_failed = False
        while True:
            missing = self._missing_java_names()
            if missing:
                messages.append(
                    Message(
                        "user",
                        f"ETAPA OBRIGATÓRIA AGORA: escreva SOMENTE {missing[0]}.java "
                        "com uma única classe. Use o bloco <write_file>; não escreva outra classe.\n"
                        + self._focused_requirements(missing[0]),
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
                return SessionReply(reply.content)
            if action.tool == "respond":
                text_reply = self._text_arg(action, "text")
                self._store.remember("assistant", text_reply)
                return SessionReply(text_reply)
            if actions_used >= 12:
                return SessionReply(
                    "Parei após doze ações neste pedido para evitar um ciclo do modelo. "
                    "Revise o estado e peça para continuar."
                )
            actions_used += 1
            try:
                result = self._execute_action(action)
            except (OSError, ValueError, PatchMismatchError, RuntimeError) as exc:
                result = f"AÇÃO RECUSADA OU FALHOU: {exc}"
            if action.tool in {"write_file", "apply_patch"}:
                wrote_in_request = True
                compile_failed = False
            elif action.tool == "compile_java":
                compile_failed = result.startswith("Falha de compilação")
                compiled_in_request = not compile_failed
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

    def handle(self, text: str) -> SessionReply:
        try:
            changes = self.memory.reconcile_sources()
            criteria_changed = self.memory.update_criteria(load_criteria(self.config))
            pdf_path = self.memory.manifest.pdf_path
            if pdf_path and not self._enunciado_invalid:
                try:
                    pdf_changed = pdf_sha256(self.workspace._resolve(Path(pdf_path))) != self.memory.manifest.pdf_hash
                except OSError:
                    pdf_changed = True
                if pdf_changed:
                    reason = "PDF mudou ou ficou indisponível; use /pdf para reler."
                    self.memory.invalidate(reason)
                    self._contract = None
                    self._pdf_text = ""
                    self._ambiguities = []
                    self._enunciado_invalid = True
                    self.evidence = EvidenceReport(unproven=[reason])
            if changes.changed or changes.added or changes.removed or criteria_changed:
                self.evidence.compiled.clear()
                self.evidence.locally_tested.clear()
            return self._dispatch(text)
        except (OSError, ValueError, RuntimeError) as error:
            return SessionReply(f"Não consegui concluir: {error}")

    def _dispatch(self, text: str) -> SessionReply:
        stripped = text.strip()
        if not stripped:
            return SessionReply("")
        lowered = stripped.casefold()
        if lowered in {"/sair", "sair"}:
            return SessionReply("Até logo.", True)
        if self._awaiting_enunciado:
            if lowered == "/fim":
                return self._finish_enunciado()
            self._enunciado_lines.append(stripped)
            return SessionReply("")
        if lowered == "/enunciado":
            self._awaiting_enunciado = True
            self._enunciado_lines = []
            return SessionReply("Cole o enunciado e termine com /fim na última linha.")
        if lowered == "/pdf":
            return self._list_pdfs()
        if lowered == "/desfazer":
            reply = self.history.undo_last()
            self.memory.reconcile_sources()
            if reply.undone:
                self.evidence.compiled.clear()
                self.evidence.locally_tested.clear()
            return SessionReply(reply.reason)
        if lowered == "/relatorio":
            return SessionReply(self.evidence.render())
        if lowered == "/contrato":
            return SessionReply(self._render_contract())
        if lowered == "/alteracoes":
            return SessionReply(self.history.render_changes())
        if lowered == "/estado":
            self.memory.reconcile_sources()
            return SessionReply(self.memory.status_summary())
        if lowered == "/memoria":
            return SessionReply(self.memory.build_context("", max_chars=4000))
        if lowered == "/ajuda":
            return SessionReply(
                "Comandos: /enunciado, /pdf, /contrato, /alteracoes, /estado, /memoria, /desfazer, /relatorio, /ajuda e /sair."
            )
        if self._awaiting_pdf_choice:
            return self._select_pdf(stripped)
        if self._ambiguities:
            if not stripped.isdigit():
                return SessionReply("Antes de gerar, escolha uma interpretação.\n" + self._ambiguity_question())
            return self._resolve_ambiguity(stripped)
        return self._chat(stripped)
