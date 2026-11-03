"""Conservative parser for common text/OCR representations of class diagrams."""

from __future__ import annotations

import re
import unicodedata

from java_assistant.core.spec import Member, Relationship, Requirement, Specification, Unit
from java_assistant.pdf.extract import PdfEvidence


_TYPE = re.compile(
    r"^\s*(class|classe|interface)\s*:?\s*([A-Za-z_À-ÿ][\wÀ-ÿ]*)"
    r"(?:\s+extends\s+([\wÀ-ÿ]+))?"
    r"(?:\s+implements\s+([\wÀ-ÿ]+(?:\s*,\s*[\wÀ-ÿ]+)*))?\s*$",
    re.IGNORECASE,
)
_FIELD = re.compile(r"^\s*([+\-#~])\s*([\wÀ-ÿ]+)\s*:\s*([^()]+?)\s*$")
_METHOD = re.compile(
    r"^\s*([+\-#~])\s*([\wÀ-ÿ]+)\s*\(([^)]*)\)\s*(?::\s*(.+?))?\s*$"
)
_INHERITANCE = re.compile(r"^\s*([\wÀ-ÿ]+)\s*<\|--\s*([\wÀ-ÿ]+)\s*$")
_HERDA_DE = re.compile(r"^\s*herda\s+de\s*:\s*([\wÀ-ÿ]+)\s*$", re.IGNORECASE)
_HEADING = re.compile(r"^([A-Za-zÀ-ÿ_][\wÀ-ÿ]*)\s*:\s*(.*)$")
_AMBIGUOUS = re.compile(r"^\s*([\wÀ-ÿ]+)\s*--\s*([\wÀ-ÿ]+)\s*$")
_SECTION_END = re.compile(
    r"^\s*(?:hierarquia\s+de\s+heran[çc]a|legenda\s+uml|"
    r"descri[çc][ãa]o\s+dos\s+m[ée]todos|instru[çc][ãa]o\s+final)\s*$",
    re.IGNORECASE,
)
_VISIBILITY = {"+": "public", "-": "private", "#": "protected", "~": "package"}
_ORIGINS = {"text": "pdf-text", "ocr": "pdf-ocr", "user": "user"}


def _fold_text(text: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(character)
    )


def _confidence(source: str) -> float:
    return 0.80 if source == "ocr" else 0.98


def _parameters(raw: str) -> tuple[tuple[str, str], ...]:
    if not raw.strip():
        return ()
    parsed: list[tuple[str, str]] = []
    for index, part in enumerate(raw.split(","), start=1):
        name_and_type = [value.strip() for value in part.split(":", 1)]
        if len(name_and_type) == 1 and name_and_type[0]:
            pieces = name_and_type[0].split()
            if len(pieces) == 2 and pieces[1].isidentifier():
                parsed.append((pieces[1], pieces[0]))
                continue
            parsed.append((f"arg{index}", name_and_type[0]))
            continue
        if len(name_and_type) != 2 or not all(name_and_type):
            continue
        parsed.append((name_and_type[0], name_and_type[1]))
    return tuple(parsed)


def requirements_for(
    text: str, units: tuple[Unit, ...], source: str
) -> tuple[Requirement, ...]:
    """Recompute requirement scopes after units come from another evidence source."""
    return UmlExtractor()._requirements(
        text.splitlines(), units, PdfEvidence(text, source, ())
    )


class UmlExtractor:
    def extract(self, evidence: PdfEvidence) -> Specification:
        units: list[Unit] = []
        relationships: list[Relationship] = []
        current_name: str | None = None
        current_kind = "class"
        members: list[Member] = []
        confidence = _confidence(evidence.source)
        lines = evidence.text.splitlines()

        def finish_unit() -> None:
            nonlocal current_name, members
            if current_name is not None:
                units.append(
                    Unit(current_name, current_kind, tuple(members), confidence=confidence)
                )
            current_name = None
            members = []

        for line in lines:
            stripped = line.strip()
            if _SECTION_END.match(stripped):
                finish_unit()
                continue
            type_match = _TYPE.match(stripped)
            if type_match:
                finish_unit()
                current_name = type_match.group(2)
                current_kind = (
                    "interface" if type_match.group(1).casefold() == "interface" else "class"
                )
                extends = type_match.group(3)
                if extends:
                    relationships.append(
                        Relationship(extends, current_name, "inheritance", confidence)
                    )
                implements = type_match.group(4)
                if implements:
                    for parent in implements.split(","):
                        relationships.append(
                            Relationship(parent.strip(), current_name, "implements", confidence)
                        )
                continue

            herda_de = _HERDA_DE.match(stripped)
            if herda_de and current_name is not None:
                relationships.append(
                    Relationship(herda_de.group(1), current_name, "inheritance", confidence)
                )
                continue

            inheritance = _INHERITANCE.match(stripped)
            if inheritance:
                relationships.append(
                    Relationship(
                        inheritance.group(1), inheritance.group(2), "inheritance", confidence
                    )
                )
                continue

            ambiguous = _AMBIGUOUS.match(stripped)
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
            method = _METHOD.match(stripped)
            if method:
                visibility = _VISIBILITY[method.group(1)]
                name = method.group(2)
                parameters = _parameters(method.group(3))
                modifiers = (
                    ("static",)
                    if name == "main"
                    and [type_name for _, type_name in parameters] == ["String[]"]
                    else ()
                )
                members.append(
                    Member(
                        name=name,
                        kind="constructor" if name == current_name else "method",
                        type_name=(method.group(4) or current_name).strip(),
                        visibility=visibility,
                        parameters=parameters,
                        modifiers=modifiers,
                    )
                )
                continue
            field = _FIELD.match(stripped)
            if field:
                members.append(
                    Member(
                        name=field.group(2),
                        kind="field",
                        type_name=field.group(3).strip(),
                        visibility=_VISIBILITY[field.group(1)],
                    )
                )

        finish_unit()
        requirements = self._requirements(lines, units, evidence)
        warnings = list(evidence.warnings)
        if not units:
            warnings.append("Nenhuma classe UML foi reconhecida com segurança.")
        if any(item.confidence < 0.9 for item in relationships):
            warnings.append("Há relacionamentos UML que exigem confirmação do usuário.")
        return Specification(
            tuple(units), tuple(relationships), requirements, tuple(warnings)
        )

    def _requirements(
        self, lines: list[str], units: list[Unit], evidence: PdfEvidence
    ) -> tuple[Requirement, ...]:
        names = {unit.name for unit in units}
        folded = {_fold_text(name): name for name in names}
        headings: dict[int, tuple[str, str]] = {}
        tail = len(lines)
        for index, raw in enumerate(lines):
            stripped = raw.strip()
            if _SECTION_END.match(stripped):
                tail = index
                break
            type_match = _TYPE.match(stripped)
            if type_match and type_match.group(2) in names:
                headings[index] = (type_match.group(2), "")
                continue
            heading = _HEADING.match(stripped)
            if heading and _fold_text(heading.group(1)) in folded:
                headings[index] = (
                    folded[_fold_text(heading.group(1))],
                    heading.group(2),
                )
                continue
            candidate = _fold_text(stripped.rstrip(":"))
            if candidate in folded:
                headings[index] = (folded[candidate], "")

        requirements: list[Requirement] = []
        scope: str | None = None
        body: list[str] = []

        def flush() -> None:
            text = "\n".join(body).strip()
            if text:
                requirements.append(
                    Requirement(
                        text=text,
                        origin=_ORIGINS.get(evidence.source, "pdf-text"),
                        confidence=_confidence(evidence.source),
                        scope=scope,
                    )
                )

        for index, raw in enumerate(lines[:tail]):
            if index in headings:
                flush()
                scope, remainder = headings[index]
                body = [remainder] if remainder else []
            else:
                body.append(raw)
        flush()
        return tuple(requirements)
