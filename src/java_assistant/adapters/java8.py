"""Java 8 adapter: generation prompt, parsing, repair hints and inspection."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Mapping

from java_assistant.core.facts import Rule
from java_assistant.core.spec import Specification, Unit, members_of
from java_assistant.java.validator import contract_issues
from java_assistant.model.client import Message

from .base import Toolchain

_PUBLIC_TYPE = re.compile(
    r"\bpublic\s+(?:abstract\s+|final\s+)?(class|interface|enum)\s+"
    r"([A-Za-z_$][A-Za-z0-9_$]*)"
)
_DIAGNOSTIC = re.compile(r"(?m)([^:\n]+\.java):\d+:\s*error")

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
- Não invente membros: getters, setters, equals, hashCode ou toString só entram se constarem das DECLARAÇÕES JAVA OBRIGATÓRIAS.
- Implemente somente atributos, construtores e métodos pedidos, com a visibilidade exata do UML.
- Se forem necessários vários arquivos, grave apenas um agora; após o resultado, grave o próximo.
- Seja compacto para a resposta não ser cortada.
- Depois de criar todos os arquivos, obrigatoriamente use compile_java e corrija qualquer erro.
- Quando houver classe main, use run_java antes de respond.
""".strip()

_GENERAL_CHECK = (
    "VERIFICAÇÃO GERAL: aumento de X% = base * (1 + X/100); redução de X% = "
    "base * (1 - X/100). Não aplique duas vezes um efeito já calculado por super. "
    "Se a classe herdar de uma superclasse sem construtor vazio, crie o construtor "
    "público mínimo que receba os dados herdados e próprios e chame super corretamente. "
    "Se o enunciado proibir ultrapassar um limite, valide e lance "
    "IllegalArgumentException em vez de ignorar o excesso. "
    "Use exatamente o atributo que o requisito cita; não o substitua por outro "
    "parecido só porque também é numérico."
)


class JavaMatchers:
    def factor(self, value: float) -> re.Pattern[str]:
        literal = re.escape(f"{value:g}")
        direct = rf"(?:\*|\*=)\s*{literal}(?:\.0+)?(?![\d.])"
        percent = ""
        if value != 1.0:
            delta = round((value - 1.0) * 100, 10)
            amount = re.escape(f"{abs(delta):g}")
            sign = r"\+" if delta > 0 else "-"
            percent = (
                rf"|\(\s*1(?:\.0+)?\s*{sign}\s*{amount}(?:\.0+)?"
                rf"\s*/\s*100(?:\.0+)?\s*\)"
            )
        return re.compile(rf"{direct}{percent}")

    def upper_bound_guard(self) -> re.Pattern[str]:
        return re.compile(
            r"(?:>|>=)(?:\s*\)?\s*\{)?[^;}]{0,200}?(?:throw|return|Math\.min\(|\?)"
            r"|Math\.min\([^ ()]+,\s*[^ ()]+\)",
            re.DOTALL,
        )

    def super_call(self, method: str) -> re.Pattern[str]:
        return re.compile(rf"super\.{re.escape(method)}\s*\(")

    def arithmetic_on_super(self, method: str) -> re.Pattern[str]:
        escaped = re.escape(method)
        inline = rf"super\.{escaped}\s*\([^;]*\)\s*[-+*/]|[-+*/]\s*super\.{escaped}"
        stored = (
            rf"\b(\w+)\s*=\s*super\.{escaped}\s*\([^;]*\)\s*;"
            rf".{{0,400}}?(?:\b\1\s*[-+*/]=|\b\1\s*[-+*/](?!=)|[-+*/]\s*\b\1\b)"
        )
        return re.compile(rf"(?:{inline})|(?:{stored})", re.DOTALL)


class Java8Adapter:
    id = "java8"
    source_extension = ".java"

    def system_protocol(self) -> str:
        return _ACTION_PROTOCOL

    def unit_contract(self, spec: Specification, unit: Unit) -> str:
        parts = [
            "UML DA CLASSE: "
            + json.dumps(
                {
                    "name": unit.name,
                    "kind": unit.kind,
                    "members": [
                        {
                            "name": member.name,
                            "kind": member.kind,
                            "type_name": member.type_name,
                            "visibility": member.visibility,
                            "parameters": [list(parameter) for parameter in member.parameters],
                            "modifiers": list(member.modifiers),
                        }
                        for member in unit.members
                    ],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        ]
        declarations = [
            f"{field.visibility} "
            + "".join(f"{modifier} " for modifier in field.modifiers)
            + f"{field.type_name} {field.name};"
            for field in members_of(unit, "field")
        ]
        for member in (
            *members_of(unit, "constructor"),
            *members_of(unit, "method"),
        ):
            parameters = ", ".join(
                f"{type_name} {parameter_name}"
                for parameter_name, type_name in member.parameters
            )
            if member.kind == "constructor":
                declarations.append(f"{member.visibility} {unit.name}({parameters});")
            else:
                declarations.append(
                    f"{member.visibility} "
                    + "".join(f"{modifier} " for modifier in member.modifiers)
                    + f"{member.type_name} {member.name}({parameters});"
                )
        if declarations:
            parts.append(
                "DECLARAÇÕES JAVA OBRIGATÓRIAS (copie tipos e visibilidades "
                "literalmente):\n" + "\n".join(declarations)
            )

        related = [
            relationship
            for relationship in spec.relationships
            if unit.name in {relationship.parent, relationship.child}
        ]
        if related:
            parts.append(
                "RELACIONAMENTOS: "
                + json.dumps(
                    [
                        {
                            "parent": item.parent,
                            "child": item.child,
                            "kind": item.kind,
                        }
                        for item in related
                    ],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        parents = [
            item.parent
            for item in spec.relationships
            if item.child == unit.name
            and item.kind == "inheritance"
            and item.confidence >= 0.9
        ]
        interfaces = [
            item.parent
            for item in spec.relationships
            if item.child == unit.name
            and item.kind == "implements"
            and item.confidence >= 0.9
        ]
        if parents or interfaces:
            abstract = "abstract " if "abstract" in unit.modifiers else ""
            header = f"public {abstract}{unit.kind} {unit.name}"
            if parents:
                header += f" extends {parents[0]}"
            if interfaces:
                header += " implements " + ", ".join(interfaces)
            parts.append("CABEÇALHO OBRIGATÓRIO: " + header)
        return "\n".join(parts)

    def build_unit_prompt(
        self,
        *,
        spec: Specification,
        unit: Unit,
        rules: tuple[Rule, ...],
        sections: Mapping[str, str],
    ) -> list[Message]:
        contract = sections.get("spec_target") or self.unit_contract(spec, unit)
        system_parts = [
            sections.get("protocol", ""),
            sections.get("criteria", ""),
            contract,
            sections.get("parents", ""),
            sections.get("pdf_excerpt", ""),
            sections.get("rules", ""),
            sections.get("memory", ""),
        ]
        system = "\n\n".join(part for part in system_parts if part)
        if system:
            system += "\n\n"
        system += (
            "Você está em modo de geração dirigida. Retorne somente o fonte solicitado; "
            "não escolha ferramentas e não antecipe outras classes."
        )
        request = (
            f"Escreva SOMENTE {unit.name}{self.source_extension}. Retorne apenas o "
            "código-fonte Java 8 completo, sem Markdown, sem tags, sem package e sem "
            f"explicações. Deve existir exatamente uma declaração pública chamada "
            f"{unit.name}. Preserve exatamente o UML e as regras abaixo.\n\n"
            f"PEDIDO ORIGINAL: {sections.get('user_request', '')}\n\n{_GENERAL_CHECK}"
        )
        return [Message("system", system), Message("user", request)]

    def parse_unit_source(self, reply: str, unit: Unit) -> str:
        candidate = reply.strip()
        write_start = re.search(
            rf'<write_file path="{re.escape(unit.name)}\{self.source_extension}">\s*',
            candidate,
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

        public_types = _PUBLIC_TYPE.findall(candidate)
        if public_types != [(unit.kind, unit.name)]:
            found = ", ".join(f"{kind} {name}" for kind, name in public_types) or "nenhuma"
            raise ValueError(
                f"Era esperada somente a declaração pública {unit.kind} {unit.name}, "
                f"mas vieram: {found}"
            )
        if "<write_file" in candidate or "<compile_java" in candidate:
            raise ValueError("A resposta misturou ações com o código Java.")
        return candidate.rstrip() + "\n"

    def structural_issues(
        self, spec: Specification, toolchain: Toolchain
    ) -> tuple[str, ...]:
        return contract_issues(spec, toolchain)

    def repair_target(self, diagnostics: str) -> str | None:
        match = _DIAGNOSTIC.search(diagnostics)
        if not match:
            return None
        path = Path(match.group(1).strip())
        return path.stem if path.suffix.casefold() == ".java" else None

    def diagnostic_hint(self, diagnostics: str) -> str:
        normalized = diagnostics.casefold()
        hints: list[str] = []
        if "int cannot be converted to double" in normalized:
            hints.append(
                "Para atribuir um int a Double em Java 8, converta antes para double, "
                "por exemplo: Double valor = (double) inteiro;"
            )
        if "cannot find symbol" in normalized:
            hints.append(
                "Confira nomes de classes, campos e métodos e a ordem de geração das "
                "unidades; nenhum símbolo novo pode ser inventado."
            )
        if "missing return" in normalized:
            hints.append("Todo caminho do método precisa retornar um valor do tipo declarado.")
        if "no suitable constructor found" in normalized or "is not applicable" in normalized:
            hints.append(
                "A superclasse não tem construtor com esses argumentos: chame um "
                "construtor existente dela passando TODOS os parâmetros (veja o arquivo "
                "da superclasse) e só depois atribua os campos próprios."
            )
        if "verificação explícita do limite" in normalized:
            hints.append(
                "Para um limite do enunciado, valide antes de atribuir e rejeite o "
                "excesso: if (valor > limite) { throw new IllegalArgumentException("
                '"acima do limite"); }'
            )
        if "deve retornar super." in normalized:
            hints.append(
                "Quando a classe não tem regra própria para um método herdado, o corpo "
                "deve ser somente return super.metodo(); sem cálculo adicional."
            )
        if "incompatible types" in normalized and "int cannot be converted" not in normalized:
            hints.append("Preserve exatamente os tipos declarados no UML.")
        return "\n".join(hints)

    def entry_point(self, spec: Specification) -> str | None:
        for unit in spec.units:
            for member in members_of(unit, "method"):
                if member.name == "main" and "static" in member.modifiers:
                    return unit.name
        return None

    def matchers(self) -> JavaMatchers:
        return JavaMatchers()
