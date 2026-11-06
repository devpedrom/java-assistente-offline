"""Generic requirements extracted from an exercise statement."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol

from .spec import Requirement, Specification, Unit, find_unit, members_of


_RULE_KINDS = frozenset({"factor", "upper_bound", "super_call", "divisor"})
_PERCENT_UP = re.compile(
    r"aument\w*\s+(?:em|de)\s+(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE
)
_PERCENT_DOWN = re.compile(
    r"redu\w*\s+(?:em|de)\s+(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE
)
_PERCENT_ACRESCIMO = re.compile(
    r"acr[ée]scimo\s+de\s+(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE
)
_PERCENT_DESCONTO = re.compile(
    r"desconto\s+de\s+(\d+(?:[.,]\d+)?)\s*%", re.IGNORECASE
)
_HALF = re.compile(r"pela\s+metade|reduzid\w*\s+pela\s+metade", re.IGNORECASE)
_DOUBLE = re.compile(
    r"\bdobra(?:r|da|do|ndo|s|m|ção|ções)?\b", re.IGNORECASE
)
_QUARTER = re.compile(r"reduzid\w*\s+em\s+um\s+quarto", re.IGNORECASE)
_UPPER_BOUND = re.compile(
    r"nunca[^.\n]*maior\s+que|n[ãa]o\s+pode\s+ser\s+maior\s+que", re.IGNORECASE
)
_DIVIDE = re.compile(
    r"divid\w*\s+pel[oa]\s+(?:(?:n[úu]mero|quantidade)\s+de\s+)?"
    r"([A-Za-zÀ-ÿ_$][\w$]*)",
    re.IGNORECASE,
)
_COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_CALL = re.compile(r"([A-Za-z_$][\w$]*)\s*\(")
_METHOD_HEADER = re.compile(
    r"^\s*(?:[+\-#~]\s*)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*(?::.*)?$"
)
_CLASS_HEADING = re.compile(
    r"^\s*(?:class|classe|interface)\b", re.IGNORECASE
)


def _strip_comments(source: str) -> str:
    """Comments are not code: they must not satisfy a textual rule.

    shortcut: a ``//`` inside a string literal is stripped too; upgrade to a
    string-aware scan if exercises start carrying URLs or ``//`` literals.
    """
    return _COMMENTS.sub("", source)


@dataclass(frozen=True, slots=True)
class Rule:
    kind: str
    unit: str | None
    value: float | None
    text: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.kind not in _RULE_KINDS:
            raise ValueError(f"Regra inválida: {self.kind!r}.")
        if self.unit is not None and not self.unit.isidentifier():
            raise ValueError(f"Unidade da regra inválida: {self.unit!r}.")
        if self.value is not None and (
            isinstance(self.value, bool) or not isinstance(self.value, (int, float))
        ):
            raise ValueError("O valor da regra precisa ser numérico ou nulo.")
        if not self.text.strip():
            raise ValueError("A regra precisa citar o texto que a originou.")


class SourceMatchers(Protocol):
    def factor(self, value: float) -> re.Pattern[str]: ...
    def upper_bound_guard(self) -> re.Pattern[str]: ...
    def super_call(self, method: str) -> re.Pattern[str]: ...
    def arithmetic_on_super(self, method: str) -> re.Pattern[str]: ...


def _literal(value: float) -> str:
    text = f"{value:g}"
    return text if "." in text else text + ".0"


def _number(raw: str) -> float:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        return float(raw.replace(".", ""))
    return float(raw.replace(",", "."))


def _effective_requirements(spec: Specification) -> tuple[Requirement, ...]:
    """User evidence supersedes PDF evidence for the same requirement scope."""
    user_scopes = {
        requirement.scope
        for requirement in spec.requirements
        if requirement.origin == "user"
    }
    return tuple(
        requirement
        for requirement in spec.requirements
        if requirement.origin == "user" or requirement.scope not in user_scopes
    )


def _block_for(text: str, position: int, unit: Unit | None) -> str:
    """The method block or paragraph that contains ``position``.

    Exercise statements often describe a whole class in prose, with a method
    header followed by conditional percentages. Binding every factor to the
    whole class text would name unrelated fields (for example the ``setor``
    line) as the base of a salary discount. Using the local block keeps each
    factor tied to the method that declares it.
    """
    lines = text.splitlines()
    if not lines:
        return text
    index = min(text.count("\n", 0, position), len(lines) - 1)

    def is_header(candidate: int) -> bool:
        return _METHOD_HEADER.match(lines[candidate]) is not None

    def is_unit_method(candidate: int) -> bool:
        match = _METHOD_HEADER.match(lines[candidate])
        if match is None:
            return False
        if unit is None:
            return True
        return any(
            member.kind == "method" and member.name == match.group(1)
            for member in members_of(unit, "method")
        )

    start: int | None = None
    for candidate in range(index, -1, -1):
        if _CLASS_HEADING.match(lines[candidate]):
            break
        if is_unit_method(candidate):
            start = candidate
            break
        if not lines[candidate].strip():
            break
    if start is None:
        start = index
        while (
            start > 0
            and lines[start - 1].strip()
            and not _CLASS_HEADING.match(lines[start - 1])
        ):
            start -= 1
        end = index + 1
        while (
            end < len(lines)
            and lines[end].strip()
            and not _CLASS_HEADING.match(lines[end])
        ):
            end += 1
        return "\n".join(lines[start:end]).strip()

    end = len(lines)
    for candidate in range(start + 1, len(lines)):
        if _CLASS_HEADING.match(lines[candidate]) or is_header(candidate):
            end = candidate
            break
        if not lines[candidate].strip():
            end = candidate
            break
    return "\n".join(lines[start:end]).strip()


def _super_call_rules(spec: Specification) -> list[Rule]:
    units = {unit.name: unit for unit in spec.units}
    rules: list[Rule] = []
    for relationship in spec.relationships:
        if relationship.kind != "inheritance" or relationship.confidence < 0.9:
            continue
        parent = units.get(relationship.parent)
        child = units.get(relationship.child)
        if parent is None or child is None:
            continue
        inherited = {member.name for member in members_of(parent, "method")}
        scoped = " ".join(
            requirement.text
            for requirement in _effective_requirements(spec)
            if requirement.scope in {None, child.name}
        ).casefold()
        for member in members_of(child, "method"):
            if member.name not in inherited:
                continue
            if re.search(rf"\b{re.escape(member.name.casefold())}\b", scoped):
                continue
            rules.append(Rule("super_call", child.name, None, member.name))
    return rules


def extract_rules(spec: Specification) -> tuple[Rule, ...]:
    """Read factors and limits from the requirement text, without domain words."""
    rules: list[Rule] = []
    seen: set[tuple[str, str | None, float | None, str, str]] = set()

    def add(
        kind: str,
        scope: str | None,
        value: float | None,
        text: str,
        detail: str = "",
    ) -> None:
        key = (kind, scope, value, text, detail)
        if key not in seen:
            seen.add(key)
            rules.append(Rule(kind, scope, value, text, detail))

    units = {unit.name: unit for unit in spec.units}
    for requirement in _effective_requirements(spec):
        text = requirement.text
        unit = units.get(requirement.scope) if requirement.scope else None

        def block(position: int) -> str:
            return _block_for(text, position, unit)

        for match in _PERCENT_UP.finditer(text):
            add(
                "factor",
                requirement.scope,
                1 + _number(match.group(1)) / 100,
                block(match.start()),
            )
        for match in _PERCENT_DOWN.finditer(text):
            add(
                "factor",
                requirement.scope,
                1 - _number(match.group(1)) / 100,
                block(match.start()),
            )
        for match in _PERCENT_ACRESCIMO.finditer(text):
            add(
                "factor",
                requirement.scope,
                1 + _number(match.group(1)) / 100,
                block(match.start()),
            )
        for match in _PERCENT_DESCONTO.finditer(text):
            add(
                "factor",
                requirement.scope,
                1 - _number(match.group(1)) / 100,
                block(match.start()),
            )
        for match in _HALF.finditer(text):
            add("factor", requirement.scope, 0.5, block(match.start()))
        for match in _DOUBLE.finditer(text):
            add("factor", requirement.scope, 2.0, block(match.start()))
        for match in _QUARTER.finditer(text):
            add("factor", requirement.scope, 0.75, block(match.start()))
        for match in _UPPER_BOUND.finditer(text):
            add("upper_bound", requirement.scope, None, block(match.start()))
        fields = _fields_of(spec, requirement.scope) if requirement.scope else ()
        for match in _DIVIDE.finditer(text):
            divisor = next(
                (
                    field
                    for field in fields
                    if field.casefold().rstrip("s") == match.group(1).casefold().rstrip("s")
                ),
                None,
            )
            if divisor is not None:
                add(
                    "divisor",
                    requirement.scope,
                    None,
                    block(match.start()),
                    divisor,
                )

    for rule in _super_call_rules(spec):
        add(rule.kind, rule.unit, rule.value, rule.text)
    return tuple(rules)


def _fields_of(spec: Specification, name: str) -> tuple[str, ...]:
    """Field names visible in a unit: its own and the inherited ones."""
    units = {unit.name: unit for unit in spec.units}
    parents = {
        relationship.child: relationship.parent
        for relationship in spec.relationships
        if relationship.kind == "inheritance"
    }
    fields: list[str] = []
    seen: set[str] = set()
    current: str | None = name
    while current is not None and current in units and current not in seen:
        seen.add(current)
        fields.extend(member.name for member in members_of(units[current], "field"))
        current = parents.get(current)
    return tuple(fields)


def _rule_method(text: str, unit: Unit) -> str | None:
    """Rule text such as ``calculo(): ...`` names the method it applies to."""
    match = re.match(r"\s*([A-Za-z_$][\w$]*)\s*(?:\([^)]*\))?\s*:", text)
    if match and any(
        member.kind == "method" and member.name == match.group(1)
        for member in unit.members
    ):
        return match.group(1)
    return None


def _named_fields(rule: Rule, unit: Unit) -> tuple[str, ...]:
    return tuple(
        member.name
        for member in members_of(unit, "field")
        if re.search(rf"\b{re.escape(member.name)}\b", rule.text)
    )


def _method_parameters(unit: Unit, method: str | None) -> tuple[str, ...]:
    if method is None:
        return ()
    for member in members_of(unit, "method"):
        if member.name == method:
            return tuple(name for name, _ in member.parameters)
    return ()


def _operand(name: str) -> str:
    """The field, ``this.field`` or its getter, never the tail of another name."""
    capitalized = name[:1].upper() + name[1:]
    return (
        rf"(?<![\w$])(?:(?:this\.)?{re.escape(name)}"
        rf"|get{re.escape(capitalized)}\s*\(\s*\))(?![\w$])"
    )


def _applies_factor(text: str, value: float, name: str) -> bool:
    """True when the literal is applied directly to ``name`` (or its getter)."""
    literal = re.escape(f"{value:g}") + r"(?:\.0+)?"
    operand = _operand(name)
    return bool(
        re.search(
            rf"(?:{operand})\s*(?:\*=|\*)\s*\(*\s*{literal}(?![\d.])"
            rf"|(?<![\d.]){literal}\s*\)*\s*\*\s*(?:{operand})",
            text,
        )
    )


def _method_body(source: str, name: str) -> str | None:
    signature = re.search(rf"\b{re.escape(name)}\s*\([^;{{}}]*\)[^;{{}}]*\{{", source)
    if signature is None:
        return None
    start = signature.end() - 1
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return None


def issues(
    rules: tuple[Rule, ...],
    unit: Unit,
    source: str,
    matchers: SourceMatchers,
    parent: Unit | None = None,
) -> tuple[str, ...]:
    source = _strip_comments(source)
    inherited: dict[str, set[float]] = {}
    if parent is not None:
        for inherited_rule in rules:
            if inherited_rule.kind != "factor" or inherited_rule.unit != parent.name:
                continue
            inherited_method = _rule_method(inherited_rule.text, parent)
            if inherited_method and inherited_rule.value is not None:
                inherited.setdefault(inherited_method, set()).add(
                    inherited_rule.value
                )
    found: list[str] = []
    for rule in rules:
        if rule.unit is not None and rule.unit != unit.name:
            continue
        if rule.kind == "factor":
            assert rule.value is not None
            method = _rule_method(rule.text, unit)
            body = _method_body(source, method) if method else None
            scoped = body if body is not None else source
            where = f"no método {method}" if body is not None else "no arquivo"
            literal = _literal(rule.value)
            # A subclass may reuse the superclass calculation instead of repeating
            # the discount: super.metodo() * acrescimo applies the inherited factor
            # once, which is exactly what the criteria demand.
            delegates_to_parent = bool(
                method
                and re.search(
                    rf"\bsuper\s*\.\s*{re.escape(method)}\s*\(", scoped
                )
                and rule.value in inherited.get(method, set())
            )
            missing_factor = (
                not matchers.factor(rule.value).search(scoped)
                and not delegates_to_parent
            )
            named = _named_fields(rule, unit)
            field_present = any(
                re.search(_operand(name), scoped) for name in named
            )
            factor_on_parameter = any(
                _applies_factor(scoped, rule.value, parameter)
                for parameter in _method_parameters(unit, method)
            )
            factor_on_field = any(
                _applies_factor(scoped, rule.value, name) for name in named
            )
            missing_field = bool(named) and (
                not field_present or (factor_on_parameter and not factor_on_field)
            )
            if missing_factor or missing_field:
                if len(named) == 1:
                    target = named[0]
                elif named:
                    target = "um dos campos citados (" + ", ".join(named) + ")"
                else:
                    target = "a base do cálculo"
                base = named[0] if named else "base"
                expected = (
                    f"exige multiplicar {target} por {literal} {where} "
                    f"(por exemplo {base} * {literal})"
                )
                found.append(f"{unit.name}: {rule.text.strip()} {expected}.")
        elif rule.kind == "upper_bound":
            if not matchers.upper_bound_guard().search(source):
                found.append(
                    f"{unit.name}: {rule.text.strip()} exige uma verificação explícita "
                    "do limite."
                )
        elif rule.kind == "divisor":
            method = _rule_method(rule.text, unit)
            body = _method_body(source, method) if method else None
            scoped = body if body is not None else source
            field = re.escape(rule.detail)
            capitalized = re.escape(
                rule.detail[:1].upper() + rule.detail[1:]
            )
            if not re.search(
                rf"/\s*(?:this\.)?(?:{field}|get{capitalized}\s*\(\s*\)|"
                rf"is{capitalized}\s*\(\s*\))(?!\w)",
                scoped,
            ):
                where = f"no método {method}" if body is not None else "no arquivo"
                found.append(
                    f"{unit.name}: {rule.text.strip()} exige dividir por "
                    f"{rule.detail} {where} (this.{rule.detail})."
                )
        elif matchers.super_call(rule.text).search(source):
            if matchers.arithmetic_on_super(rule.text).search(source):
                found.append(
                    f"{unit.name}: {rule.text} não pode aplicar novo cálculo sobre "
                    f"super.{rule.text}() sem um requisito desta classe."
                )
        elif re.search(rf"\b{re.escape(rule.text)}\s*\([^)]*\)\s*\{{", source):
            found.append(
                f"{unit.name}: {rule.text} sobrescreve o método herdado e deve "
                f"retornar super.{rule.text}()."
            )
    return tuple(found)


def _foreign_method_entries(
    spec: Specification, requirement: Requirement
) -> list[tuple[str, str]]:
    """Where cited helper methods live, when not on the requirement's own unit."""
    own = find_unit(spec, requirement.scope) if requirement.scope else None
    cited = set(_CALL.findall(requirement.text))
    entries: list[tuple[str, str]] = []
    for unit in spec.units:
        if own is not None and unit.name == own.name:
            continue
        for member in members_of(unit, "method"):
            if member.name in cited:
                signature = ", ".join(type_name for _, type_name in member.parameters)
                entries.append((f"{member.name}({signature})", unit.name))
    return list(dict.fromkeys(entries))


def requirements_section(spec: Specification, unit: Unit) -> str:
    """Confirmed requirement text for the unit, scoped first, then general."""
    selected = [
        requirement
        for requirement in _effective_requirements(spec)
        if requirement.scope in {None, unit.name}
    ]
    selected.sort(key=lambda requirement: requirement.scope is None)
    if not selected:
        return ""
    lines = ["REQUISITOS APLICÁVEIS:"]
    for requirement in selected:
        scope = requirement.scope or "geral"
        lines.append(f"[{requirement.origin} | {scope}] {requirement.text}")
        entries = _foreign_method_entries(spec, requirement)
        if entries:
            owners = "; ".join(
                f"{signature} -> {owner}" for signature, owner in entries
            )
            names = ", ".join(
                dict.fromkeys(signature.split("(", 1)[0] for signature, _ in entries)
            )
            lines.append("Métodos citados pertencem a: " + owners)
            lines.append(
                f"Use exatamente estes nomes, sem renomear: {names}. Chame cada um "
                "no objeto já convertido para a classe que o declara, por exemplo "
                "((Subclasse) objeto).metodo(texto); nunca no tipo base e nunca "
                "repetindo o método que está sendo escrito."
            )
    return "\n".join(lines)


def prompt_section(rules: tuple[Rule, ...], unit: Unit) -> str:
    factor_groups: dict[str | None, list[Rule]] = {}
    upper_bound: list[str] = []
    super_call: list[str] = []
    divisor: list[str] = []
    for rule in rules:
        if rule.unit is not None and rule.unit != unit.name:
            continue
        if rule.kind == "factor":
            assert rule.value is not None
            factor_groups.setdefault(_rule_method(rule.text, unit), []).append(rule)
        elif rule.kind == "upper_bound":
            upper_bound.append(
                f"{rule.text.strip()} => valide explicitamente e rejeite o valor "
                "que exceder o limite"
            )
        elif rule.kind == "divisor":
            method = _rule_method(rule.text, unit)
            where = f" (no método {method})" if method else ""
            divisor.append(f"{rule.text.strip()} => base / {rule.detail}{where}")
        else:
            super_call.append(f"{rule.text}: retorne somente super.{rule.text}()")

    parts: list[str] = []
    if factor_groups:
        block: list[str] = []
        for method, group in factor_groups.items():
            where = f"método {method}" if method else "cálculo"
            block.append(f"[{where}]")
            for text in dict.fromkeys(rule.text.strip() for rule in group):
                block.append(text)
            factors: list[str] = []
            for rule in group:
                named = _named_fields(rule, unit)
                base = named[0] if len(named) == 1 else "base"
                factors.append(f"{base} * {_literal(rule.value)}")
            block.append(
                "Aplique TODOS estes fatores em cada caminho de execução, "
                "multiplicando-os: " + "; ".join(dict.fromkeys(factors))
            )
            if len(group) > 1:
                block.append(
                    "Se as categorias são alternativas (por exemplo SENIOR/JUNIOR), use "
                    "if/else: em cada ramo aplique o fator daquela categoria MAIS todos "
                    "os fatores comuns (como o desconto). Em um ramo sem acréscimo, "
                    "use o fator 1.0 e ainda aplique os descontos comuns."
                )
        parts.append("FATOS ARITMÉTICOS OBRIGATÓRIOS:\n" + "\n".join(block))
    if upper_bound:
        parts.append("LIMITES OBRIGATÓRIOS:\n" + "\n".join(upper_bound))
    if super_call:
        parts.append("SOBRESCRITA SEM NOVO EFEITO:\n" + "\n".join(super_call))
    if divisor:
        parts.append("DIVISÕES OBRIGATÓRIAS:\n" + "\n".join(divisor))
    return "\n".join(parts)
