"""Versioned, validated canonical memory documents."""

from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath
import re

from java_assistant.uml.models import JavaContract, contract_from_dict, contract_to_dict

SCHEMA_VERSION = 1


def _schema(data):
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Memória com versão de esquema inválida.")


def _text(value, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Campo textual inválido na memória.")
    return value


def _hash(value):
    if value is not None and (not isinstance(value, str) or not re.fullmatch(r"(?:texto-)?[0-9a-f]{64}", value)):
        raise ValueError("Hash inválido na memória.")
    return value


def _hashes(values):
    if not isinstance(values, dict):
        raise ValueError("Inventário inválido.")
    for path, digest in values.items():
        if not isinstance(path, str) or "\\" in path or ":" in path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts or not path.endswith(".java"):
            raise ValueError("Caminho inválido no inventário.")
        if _hash(digest) is None:
            raise ValueError("Hash ausente no inventário.")
    return dict(values)


def _strings(values):
    if not isinstance(values, (list, tuple)) or any(not isinstance(value, str) for value in values):
        raise ValueError("Lista textual inválida.")
    return tuple(values)


@dataclass(frozen=True)
class ProjectManifest:
    project_id: str
    pdf_path: str | None = None
    pdf_hash: str | None = None
    criteria_hash: str | None = None
    schema_version: int = SCHEMA_VERSION

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        _schema(data)
        identity = _text(data.get("project_id"))
        if not identity.strip():
            raise ValueError("Identidade vazia.")
        path = _text(data.get("pdf_path"), optional=True)
        if path is not None and (not path or "/" in path or "\\" in path or ":" in path or path in (".", "..")):
            raise ValueError("Caminho de PDF inválido.")
        return cls(identity, path, _hash(data.get("pdf_hash")), _hash(data.get("criteria_hash")))


@dataclass(frozen=True)
class RequirementSnapshot:
    contract: JavaContract
    text: str
    source: str
    identity: str
    version: int = 1
    schema_version: int = SCHEMA_VERSION

    def to_dict(self):
        return {**asdict(self), "contract": contract_to_dict(self.contract)}

    @classmethod
    def from_dict(cls, data):
        _schema(data)
        version = data.get("version", 1)
        if type(version) is not int or version < 1:
            raise ValueError("Versão de requisitos inválida.")
        try:
            return cls(contract_from_dict(data["contract"]), _text(data["text"]), _text(data["source"]), _hash(data["identity"]), version)
        except KeyError as error:
            raise ValueError("Requisitos incompletos.") from error


@dataclass(frozen=True)
class SessionState:
    phase: str = "novo"
    source_hashes: dict = field(default_factory=dict)
    next_action: str = "Carregue o enunciado com /pdf ou /enunciado."
    last_operation: str = ""
    target_class: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        object.__setattr__(self, "source_hashes", _hashes(self.source_hashes))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        _schema(data)
        return cls(_text(data.get("phase", "novo")), _hashes(data.get("source_hashes", {})),
                   _text(data.get("next_action", "")), _text(data.get("last_operation", "")),
                   _text(data.get("target_class"), optional=True))


@dataclass(frozen=True)
class VerificationSnapshot:
    source_hashes: dict = field(default_factory=dict)
    compiled: bool = False
    structural: bool = False
    locally_tested: tuple[str, ...] = ()
    unproven: tuple[str, ...] = ()
    diagnostics: str = ""
    requirement_hash: str | None = None
    criteria_hash: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        object.__setattr__(self, "source_hashes", _hashes(self.source_hashes))
        object.__setattr__(self, "locally_tested", _strings(self.locally_tested))
        object.__setattr__(self, "unproven", _strings(self.unproven))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        _schema(data)
        if any(type(data.get(key, False)) is not bool for key in ("compiled", "structural")):
            raise ValueError("Resultado de verificação inválido.")
        return cls(_hashes(data.get("source_hashes", {})), data.get("compiled", False), data.get("structural", False),
                   _strings(data.get("locally_tested", ())), _strings(data.get("unproven", ())),
                   _text(data.get("diagnostics", "")), _hash(data.get("requirement_hash")), _hash(data.get("criteria_hash")))
