"""Conservative parser for common text/OCR representations of class diagrams."""

from __future__ import annotations

import re

from java_assistant.pdf.extract import PdfEvidence

from .models import JavaClass, JavaContract, JavaMember, Relationship


_CLASS = re.compile(r"^\s*(?:class|classe)\s+([A-Za-z_À-ÿ][\wÀ-ÿ]*)\s*$", re.IGNORECASE)
_FIELD = re.compile(r"^\s*([+\-#~])\s*([\wÀ-ÿ]+)\s*:\s*([^()]+?)\s*$")
_METHOD = re.compile(
    r"^\s*([+\-#~])\s*([\wÀ-ÿ]+)\s*\(([^)]*)\)\s*(?::\s*(.+?))?\s*$"
)
_INHERITANCE = re.compile(r"^\s*([\wÀ-ÿ]+)\s*<\|--\s*([\wÀ-ÿ]+)\s*$")
_AMBIGUOUS = re.compile(r"^\s*([\wÀ-ÿ]+)\s*--\s*([\wÀ-ÿ]+)\s*$")
_VISIBILITY = {"+": "public", "-": "private", "#": "protected", "~": "package"}


def _parameters(raw: str) -> tuple[tuple[str, str], ...]:
    if not raw.strip():
        return ()
    parsed: list[tuple[str, str]] = []
    for part in raw.split(","):
        name_and_type = [value.strip() for value in part.split(":", 1)]
        if len(name_and_type) != 2 or not all(name_and_type):
            continue
        parsed.append((name_and_type[0], name_and_type[1]))
    return tuple(parsed)


class UmlExtractor:
    def extract(self, evidence: PdfEvidence) -> JavaContract:
        classes: list[JavaClass] = []
        relationships: list[Relationship] = []
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

        for raw_line in evidence.text.splitlines():
            line = raw_line.strip()
            class_match = _CLASS.match(line)
            if class_match:
                finish_class()
                current_name = class_match.group(1)
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
                        alternatives=("association", "aggregation", "composition"),
                    )
                )
                continue

            if current_name is None:
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
        warnings = list(evidence.warnings)
        if not classes:
            warnings.append("Nenhuma classe UML foi reconhecida com segurança.")
        if any(item.confidence < 0.9 for item in relationships):
            warnings.append("Há relacionamentos UML que exigem confirmação do usuário.")
        return JavaContract(tuple(classes), tuple(relationships), tuple(warnings))
