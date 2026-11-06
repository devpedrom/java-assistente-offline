"""Conservative parser for common text/OCR representations of class diagrams."""

from __future__ import annotations

import re
from dataclasses import replace

from java_assistant.pdf.extract import PdfEvidence

from .models import JavaClass, JavaContract, JavaMember, Relationship


_CLASS = re.compile(
    r"^\s*(?:class|classe)\s*:?\s*([A-Za-z_À-ÿ][\wÀ-ÿ]*)\s*$",
    re.IGNORECASE,
)
_HEADING = re.compile(r"^(?:#{1,6}\s+([\wÀ-ÿ]+)|([\wÀ-ÿ]+):?)$")
_JAVA_FIELD = re.compile(r"^(public|private|protected)\s+([\wÀ-ÿ.$<>\[\]]+)\s+([\wÀ-ÿ]+)\s*;$")
_JAVA_METHOD = re.compile(
    r"^(public|private|protected)\s+(?:([\wÀ-ÿ.$<>\[\]]+)\s+)?([\wÀ-ÿ]+)\s*\(([^)]*)\)\s*;?$"
)
_FIELD = re.compile(r"^\s*([+\-#~])\s*([\wÀ-ÿ]+)\s*:\s*([^()]+?)\s*$")
_METHOD = re.compile(
    r"^\s*([+\-#~])\s*([\wÀ-ÿ]+)\s*\(([^)]*)\)\s*(?::\s*(.+?))?\s*$"
)
_INHERITANCE = re.compile(r"^\s*([\wÀ-ÿ]+)\s*<\|--\s*([\wÀ-ÿ]+)\s*$")
_HERDA_DE = re.compile(r"^\s*herda\s+de\s*:\s*([\wÀ-ÿ]+)\s*$", re.IGNORECASE)
_AMBIGUOUS = re.compile(r"^\s*([\wÀ-ÿ]+)\s*--\s*([\wÀ-ÿ]+)\s*$")
_SECTION_END = re.compile(
    r"^\s*(?:hierarquia\s+de\s+heran[çc]a|legenda\s+uml|"
    r"descri[çc][ãa]o\s+dos\s+m[ée]todos|instru[çc][ãa]o\s+final)\s*$",
    re.IGNORECASE,
)
_VISIBILITY = {"+": "public", "-": "private", "#": "protected", "~": "package"}


def _parameters(raw: str) -> tuple[tuple[str, str], ...]:
    if not raw.strip():
        return ()
    parsed: list[tuple[str, str]] = []
    for index, part in enumerate(raw.split(","), start=1):
        name_and_type = [value.strip() for value in part.split(":", 1)]
        if len(name_and_type) == 1 and name_and_type[0]:
            java_parameter = name_and_type[0].rsplit(None, 1)
            if len(java_parameter) == 2:
                parsed.append((java_parameter[1], java_parameter[0]))
            else:
                parsed.append((f"arg{index}", name_and_type[0]))
            continue
        if len(name_and_type) != 2 or not all(name_and_type):
            continue
        parsed.append((name_and_type[0], name_and_type[1]))
    return tuple(parsed)


class UmlExtractor:
    def extract(self, evidence: PdfEvidence) -> JavaContract:
        classes: list[JavaClass] = []
        relationships: list[Relationship] = []
        warnings = list(evidence.warnings)
        current_name: str | None = None
        fields: list[JavaMember] = []
        methods: list[JavaMember] = []

        def finish_class() -> None:
            nonlocal current_name, fields, methods
            if current_name is not None:
                classes.append(JavaClass(current_name, tuple(fields), tuple(methods)))
            current_name = None
            fields = []
            methods = []

        text_has_members = any(pattern.match(line.strip()) for line in evidence.text.splitlines()
                               for pattern in (_FIELD, _METHOD, _JAVA_FIELD, _JAVA_METHOD))
        combined = (evidence.text + "\n" + evidence.diagram_text
                    if evidence.diagram_text and text_has_members else evidence.diagram_text or evidence.text)
        lines = combined.splitlines()
        for index, raw_line in enumerate(lines):
            line = raw_line.strip()
            if _SECTION_END.match(line):
                finish_class()
                continue
            class_match = _CLASS.match(line)
            if class_match:
                finish_class()
                current_name = class_match.group(1)
                continue
            if re.match(r"^(?:class|classe)\b", line, re.I):
                finish_class()
                warnings.append("Declaração de classe ilegível; confirme o diagrama ou forneça o texto.")
                continue
            heading = _HEADING.match(line)
            if heading:
                next_line = next((item.strip() for item in lines[index + 1:] if item.strip()), "")
                if any(pattern.match(next_line) for pattern in (_FIELD, _METHOD, _JAVA_FIELD, _JAVA_METHOD)):
                    finish_class()
                    current_name = heading.group(1) or heading.group(2)
                    continue

            herda_de = _HERDA_DE.match(line)
            if herda_de and current_name is not None:
                relationships.append(
                    Relationship(
                        parent=herda_de.group(1),
                        child=current_name,
                        kind="inheritance",
                        confidence=0.98,
                    )
                )
                continue

            inheritance = _INHERITANCE.match(line)
            if inheritance:
                relationships.append(
                    Relationship(
                        parent=inheritance.group(1),
                        child=inheritance.group(2),
                        kind="inheritance",
                        confidence=0.98,
                    )
                )
                continue

            ambiguous = _AMBIGUOUS.match(line)
            if ambiguous:
                relationships.append(
                    Relationship(
                        parent=ambiguous.group(1),
                        child=ambiguous.group(2),
                        kind="ambiguous",
                        confidence=0.5,
                        alternatives=(("inheritance", "association", "aggregation", "composition")
                                      if evidence.diagram_text else ("association", "aggregation", "composition")),
                    )
                )
                continue

            if current_name is None:
                continue
            java_method = _JAVA_METHOD.match(line)
            if java_method:
                visibility, return_type, name, parameters = java_method.groups()
                if return_type is not None or name == current_name:
                    methods.append(JavaMember(name, return_type or current_name, visibility, _parameters(parameters)))
                continue
            java_field = _JAVA_FIELD.match(line)
            if java_field:
                visibility, type_name, name = java_field.groups()
                fields.append(JavaMember(name, type_name, visibility))
                continue
            method = _METHOD.match(line)
            if method:
                methods.append(
                    JavaMember(
                        name=method.group(2),
                        type_name=(method.group(4) or current_name).strip(),
                        visibility=_VISIBILITY[method.group(1)],
                        parameters=_parameters(method.group(3)),
                    )
                )
                continue
            field = _FIELD.match(line)
            if field:
                fields.append(
                    JavaMember(
                        name=field.group(2),
                        type_name=field.group(3).strip(),
                        visibility=_VISIBILITY[field.group(1)],
                    )
                )

        finish_class()
        merged: dict[str, JavaClass] = {}
        def combine_members(before, after):
            members = {(item.name, tuple(kind for _, kind in item.parameters)): item for item in before}
            for item in after:
                key = (item.name, tuple(kind for _, kind in item.parameters))
                previous = members.get(key)
                if previous and (previous.type_name, previous.visibility) != (item.type_name, item.visibility):
                    raise ValueError(f"UML textual e visual divergem em {item.name}; confirme o tipo e a visibilidade.")
                members.setdefault(key, item)
            return tuple(members.values())
        for item in classes:
            previous = merged.get(item.name)
            merged[item.name] = (JavaClass(item.name, combine_members(previous.fields, item.fields),
                                          combine_members(previous.methods, item.methods)) if previous else item)
        classes = list(merged.values())
        relationships = list(dict.fromkeys(relationships))
        for _ in classes:
            added = False
            for index, child in enumerate(classes):
                if any(method.name == child.name for method in child.methods):
                    continue
                parents = [item.parent for item in relationships
                           if item.child == child.name and item.kind == "inheritance" and item.confidence >= .9]
                if len(parents) != 1:
                    continue
                parent = next((item for item in classes if item.name == parents[0]), None)
                constructors = [method for method in parent.methods if method.name == parent.name] if parent else []
                if len(constructors) != 1 or not constructors[0].parameters:
                    continue
                parameters = list(constructors[0].parameters)
                for field in child.fields:
                    used = {n for n, _ in parameters}
                    name = field.name
                    suffix = len(parameters)+1
                    while name in used:
                        name = f"arg{suffix}"
                        suffix += 1
                    parameters.append((name, field.type_name))
                constructor = JavaMember(child.name, child.name, "public", tuple(parameters))
                classes[index] = replace(child, methods=(*child.methods, constructor))
                warnings.append(f"Construtor inferido para {child.name}: dados herdados e atributos próprios; confirme a assinatura.")
                added = True
            if not added:
                break
        if not classes:
            warnings.append("Nenhuma classe UML foi reconhecida com segurança.")
        if any(item.confidence < 0.9 for item in relationships):
            warnings.append("Há relacionamentos UML que exigem confirmação do usuário.")
        return JavaContract(tuple(classes), tuple(relationships), tuple(warnings))
