"""Bounded local checks from inferred, contract-checked model proposals."""

from dataclasses import asdict, dataclass
import json
import math
import re
from uuid import uuid4

from java_assistant.model.client import Message
from java_assistant.uml.models import JavaContract, JavaMember
from .validator import ContractValidator


@dataclass(frozen=True)
class RuleCase:
    class_name: str
    constructor_args: tuple
    method: str | None
    args: tuple
    expected: object
    evidence: str
    exception: str | None = None
    steps: tuple = ()


@dataclass(frozen=True)
class JudgeReport:
    passed: tuple[str, ...]
    failed: tuple[str, ...]
    unverified: tuple[str, ...]


def _literal(value, type_name: str) -> str:
    kind = type_name.removeprefix("java.lang.")
    if value is None and kind in {"Double", "Float", "Long", "Integer", "Short", "Byte", "Boolean", "String"}:
        return f"({type_name}) null"
    primitives = {"Double": "double", "Float": "float", "Long": "long", "Integer": "int",
                  "Short": "short", "Byte": "byte", "Boolean": "boolean"}
    if kind in primitives:
        return f"java.lang.{kind}.valueOf({_literal(value, primitives[kind])})"
    if kind in {"boolean", "Boolean"} and type(value) is bool:
        return "true" if value else "false"
    if kind == "String" and isinstance(value, str) and len(value) <= 500:
        # UTF-16 character literals avoid Java's pre-lexical Unicode escapes.
        encoded = value.encode("utf-16-be")
        chars = ",".join(f"(char){int.from_bytes(encoded[i:i+2], 'big')}" for i in range(0, len(encoded), 2))
        return f"new String(new char[]{{{chars}}})"
    if type(value) in (int, float) and math.isfinite(value):
        if kind in {"double", "Double", "float", "Float"}:
            return f"{float(value)!r}" + ("f" if kind in {"float", "Float"} else "d")
        bounds = {"byte": 8, "Byte": 8, "short": 16, "Short": 16,
                  "int": 32, "Integer": 32, "long": 64, "Long": 64}
        bits = bounds.get(kind)
        if bits and int(value) == value and -(2 ** (bits - 1)) <= value < 2 ** (bits - 1):
            literal = str(int(value))
            if kind in {"long", "Long"}:
                return literal + "L"
            if kind in {"byte", "Byte", "short", "Short"}:
                return f"({kind.lower()}){literal}"
            return literal
    raise ValueError(f"Literal ou tipo não suportado: {type_name}")


class Judge:
    def __init__(self, toolchain, model) -> None:
        self.toolchain = toolchain
        self.model = model
        self.unverified: list[str] = []
        self.contract: JavaContract | None = None

    def _methods(self, name: str, seen=()) -> tuple[JavaMember, ...]:
        if name in seen or self.contract is None:
            return ()
        owner = next((item for item in self.contract.classes if item.name == name), None)
        if owner is None:
            raise ValueError("Classe ausente do contrato")
        inherited = tuple(
            method for relation in self.contract.relationships
            if relation.child == name and relation.kind == "inheritance" and relation.confidence >= .9
            for method in self._methods(relation.parent, (*seen, name))
            if method.name != relation.parent
        )
        return owner.methods + inherited

    def _arguments(self, owner: str, method: str, args: tuple) -> tuple[JavaMember, str]:
        for member in self._methods(owner):
            if member.name != method or member.visibility != "public" or len(member.parameters) != len(args):
                continue
            try:
                literals = [_literal(value, kind) for value, (_, kind) in zip(args, member.parameters)]
            except ValueError:
                continue
            return member, ", ".join(literals)
        if owner == method and not args and not any(m.name == owner for m in self._methods(owner)):
            return JavaMember(owner, owner, "public"), ""
        raise ValueError(f"Assinatura pública/literais não suportados: {owner}.{method}")

    def _body(self, case: RuleCase) -> str:
        _, constructor = self._arguments(case.class_name, case.class_name, case.constructor_args)
        lines = [f"{case.class_name} instance = new {case.class_name}({constructor});"]
        for name, args in case.steps:
            _, values = self._arguments(case.class_name, name, args)
            lines.append(f"instance.{name}({values});")
        if case.method is not None:
            member, values = self._arguments(case.class_name, case.method, case.args)
            if member.type_name == "void":
                if not case.exception:
                    raise ValueError("Método void precisa de observação posterior")
                lines.append(f"instance.{case.method}({values});")
            else:
                expected = _literal(case.expected, member.type_name)
                lines.append(f"Object actual = instance.{case.method}({values});")
                lines.append(f"Object expected = {expected};")
                lines.append("if (!matches(actual, expected)) throw new AssertionError(\"resultado divergente: \" + actual + \" esperado: \" + expected);")
        elif not case.exception:
            raise ValueError("Caso sem observação ou exceção")
        return "\n".join(lines)

    def build_cases(self, contract: JavaContract, enunciado: str) -> list[RuleCase]:
        self.contract = contract
        self.unverified = ["Cobertura completa das regras e testes dos jurados não comprovada."]
        if not re.search(r"regra|%|nunca|metade|quarto|exce[çc][ãa]o", enunciado, re.I):
            self.unverified.append("Nenhuma regra de comportamento reconhecida para propor casos.")
            return []
        prompt = (
            'Proponha até 3 testes locais INFERIDOS, somente JSON {"cases": [...]}. '
            'Não escreva Java nem ferramentas. Cada caso: class_name, constructor_args (lista de literais), '
            'method (nome ou null para testar construtor), args (lista), expected (literal), '
            'evidence (citação literal curta, até 80 caracteres), exception (null ou IllegalArgumentException). '
            'steps é uma lista opcional de {"method": nome, "args": lista} executada antes da observação. '
            'Use steps para métodos void e observe o estado por um método público. '
            'Não invente valores esperados nem assinaturas. Sem dados suficientes, retorne cases vazio. '
            'Cubra ramos, composição de herança e limites quando descritos. Somente tipos escalares/String.\n'
            + json.dumps(asdict(contract), ensure_ascii=False) + "\nENUNCIADO:\n" + enunciado
        )
        try:
            reply = self.model.complete([Message("user", prompt)], max_tokens=800)
            if reply.truncated or len(reply.content) > 16000:
                raise ValueError("proposta cortada ou grande demais")
            content = reply.content.strip()
            fenced = re.fullmatch(r"```(?:json)?\s*\n(.*)\n```", content, flags=re.S | re.I)
            data = json.loads(fenced.group(1) if fenced else content)
            proposals = data["cases"]
            if not isinstance(proposals, list) or len(proposals) > 3:
                raise ValueError("lista de casos inválida")
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as error:
            self.unverified.append(f"Não foi possível propor casos: {error}")
            return []
        cases = []
        for proposal in proposals:
            try:
                if not isinstance(proposal, dict):
                    raise ValueError("caso não é objeto")
                quote = proposal["evidence"]
                if not isinstance(quote, str) or len(quote.strip()) < 8 or quote not in enunciado:
                    raise ValueError("citação ausente do enunciado")
                exception = proposal.get("exception")
                if exception not in (None, "IllegalArgumentException", "IllegalStateException", "NullPointerException"):
                    raise ValueError("exceção não suportada")
                constructor_args, args, steps = proposal["constructor_args"], proposal["args"], proposal.get("steps", [])
                if not all(isinstance(item, list) and len(item) <= 12 for item in (constructor_args, args, steps)):
                    raise ValueError("argumentos inválidos")
                parsed_steps = []
                for step in steps:
                    if not isinstance(step, dict) or not isinstance(step.get("args"), list):
                        raise ValueError("etapa inválida")
                    parsed_steps.append((step["method"], tuple(step["args"])))
                case = RuleCase(proposal["class_name"], tuple(constructor_args), proposal["method"],
                                tuple(args), proposal["expected"], quote, exception, tuple(parsed_steps))
                self._body(case)
                cases.append(case)
            except (ValueError, KeyError, TypeError, OverflowError, UnicodeError) as error:
                self.unverified.append(f"Caso proposto recusado: {error}")
        if not cases:
            self.unverified.append("Nenhum caso de comportamento com dados suficientes.")
        covered = {case.class_name for case in cases}
        self.unverified.extend(f"Comportamento sem caso local: {item.name}." for item in contract.classes if item.name not in covered)
        return cases

    def run(self, cases: list[RuleCase]) -> JudgeReport:
        passed: list[str] = []
        failed: list[str] = []
        if not cases or self.contract is None:
            return JudgeReport((), (), tuple(self.unverified or ["Nenhum caso executado."]))
        validation = ContractValidator(self.toolchain).validate(self.contract, self.toolchain.root)
        if not validation.valid:
            return JudgeReport((), validation.issues, tuple(self.unverified))
        for case in cases:
            label = f"{case.class_name}.{case.method or '<init>'} (caso inferido: {case.evidence})"
            name = "AssistenteVerificacao" + uuid4().hex
            body = self._body(case)
            if case.exception:
                body = ("boolean caught = false; try {\n" + body
                        + f"\n}} catch ({case.exception} expectedError) {{ caught = true; }}"
                        + '\nif (!caught) throw new AssertionError("exceção esperada: ' + case.exception + '");')
            source = f"""public class {name} {{
static boolean matches(Object actual, Object expected) {{
  if (expected instanceof Byte || expected instanceof Short || expected instanceof Integer || expected instanceof Long)
    return java.util.Objects.equals(actual, expected);
  if (actual instanceof Number && expected instanceof Number) {{
    double a = ((Number)actual).doubleValue(), e = ((Number)expected).doubleValue();
    return !Double.isNaN(a) && !Double.isInfinite(a) && Math.abs(a-e) <= 1e-8 * Math.max(1, Math.abs(e));
  }}
  return java.util.Objects.equals(actual, expected);
}}
public static void main(String[] args) throws Exception {{
{body}
}}
}}"""
            result = self.toolchain.run_harness(name, source, timeout_s=5)
            if result.success:
                passed.append(label)
            else:
                failed.append(label + ": " + (result.stderr or result.stdout or "timeout")[-2000:])
        return JudgeReport(tuple(passed), tuple(failed), tuple(self.unverified))
