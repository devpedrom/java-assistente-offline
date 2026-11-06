"""Small immutable model for a Java-oriented UML contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re


@dataclass(frozen=True)
class JavaMember:
    name: str
    type_name: str
    visibility: str
    parameters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class JavaClass:
    name: str
    fields: tuple[JavaMember, ...]
    methods: tuple[JavaMember, ...]


@dataclass(frozen=True)
class Relationship:
    parent: str
    child: str
    kind: str
    confidence: float
    alternatives: tuple[str, ...] = ()


@dataclass(frozen=True)
class JavaContract:
    classes: tuple[JavaClass, ...]
    relationships: tuple[Relationship, ...]
    warnings: tuple[str, ...] = ()


def contract_to_dict(contract: JavaContract) -> dict:
    return json.loads(json.dumps(asdict(contract), ensure_ascii=False))


def contract_from_dict(data: dict) -> JavaContract:
    def name(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_$À-ÿ][\w$À-ÿ]*", value):
            raise ValueError("Nome Java inválido no contrato.")
        return value

    def sequence(value):
        if not isinstance(value, list):
            raise ValueError("Sequência inválida no contrato.")
        return value

    def type_name(value):
        if not isinstance(value, str) or not re.fullmatch(r"[\w$À-ÿ.<>?, \[\]]+", value):
            raise ValueError("Tipo Java inválido no contrato.")
        return value

    def member(item):
        visibility = item["visibility"]
        if visibility not in ("public", "private", "protected", "package"):
            raise ValueError("Visibilidade inválida.")
        parameters = []
        for pair in sequence(item.get("parameters", [])):
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError("Parâmetro inválido.")
            parameters.append((name(pair[0]), type_name(pair[1])))
        return JavaMember(name(item["name"]), type_name(item["type_name"]), visibility, tuple(parameters))

    try:
        classes = tuple(JavaClass(name(item["name"]), tuple(member(m) for m in sequence(item["fields"])),
                                  tuple(member(m) for m in sequence(item["methods"])))
                        for item in sequence(data["classes"]))
        relations = []
        for item in sequence(data["relationships"]):
            confidence = item["confidence"]
            kind = item["kind"]
            alternatives = sequence(item.get("alternatives", []))
            if (type(confidence) not in (int, float) or not 0 <= confidence <= 1
                    or kind not in ("inheritance", "association", "aggregation", "composition", "ambiguous")
                    or any(a not in ("inheritance", "association", "aggregation", "composition") for a in alternatives)):
                raise ValueError("Relacionamento inválido.")
            relations.append(Relationship(name(item["parent"]), name(item["child"]), kind, confidence, tuple(alternatives)))
        warnings = sequence(data.get("warnings", []))
        if any(not isinstance(w, str) for w in warnings):
            raise ValueError("Aviso inválido.")
        return JavaContract(classes, tuple(relations), tuple(warnings))
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Contrato incompleto ou inválido.") from error
