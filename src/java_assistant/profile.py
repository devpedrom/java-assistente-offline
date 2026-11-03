"""Declarative competition profile: schema, validation, merge and paths."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .config import AppConfig


DEFAULT_SECTIONS = MappingProxyType(
    {
        "protocol": 220,
        "criteria": 400,
        "spec_target": 520,
        "parents": 800,
        "pdf_excerpt": 520,
        "rules": 300,
        "memory": 120,
        "user_request": 180,
    }
)
DEFAULT_COMMANDS = MappingProxyType(
    {
        "pdf": ("/pdf",),
        "undo": ("/desfazer",),
        "report": ("/relatorio",),
        "profile": ("/perfil",),
        "help": ("/ajuda",),
        "exit": ("/sair", "sair"),
    }
)
COMMAND_IDS = tuple(DEFAULT_COMMANDS)
_TOP_KEYS = frozenset(
    {
        "schema_version",
        "language",
        "toolchain",
        "libraries",
        "limits",
        "context",
        "commands",
    }
)
_TOOLCHAIN_KEYS = ("compiler", "runtime", "inspector")
_LIMIT_RANGES = {
    "compile_timeout_s": (1, 600),
    "run_timeout_s": (1, 600),
    "inspect_timeout_s": (1, 600),
    "repair_attempts": (0, 5),
    "max_files": (1, 500),
    "context_tokens": (512, 8192),
    "output_tokens": (64, 2048),
}


class ProfileError(ValueError):
    """Raised when the profile is missing, malformed or unusable."""


@dataclass(frozen=True)
class Limits:
    compile_timeout_s: int = 30
    run_timeout_s: int = 15
    inspect_timeout_s: int = 10
    repair_attempts: int = 2
    max_files: int = 40
    context_tokens: int = 4096
    output_tokens: int = 640


@dataclass(frozen=True)
class ContextSettings:
    chars_per_token: float = 3.5
    sections: Mapping[str, int] = DEFAULT_SECTIONS


@dataclass(frozen=True)
class Profile:
    language_id: str
    source_extension: str
    toolchain: Mapping[str, Path]
    libraries: tuple[Path, ...]
    limits: Limits
    context: ContextSettings
    commands: Mapping[str, tuple[str, ...]]
    origin: str
    global_path: Path
    project_path: Path | None


def _default_data() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "language": {"id": "java8", "source_extension": ".java"},
        "toolchain": {key: f"tools/native/bin/{name}" for key, name in (
            ("compiler", "javac"),
            ("runtime", "java"),
            ("inspector", "javap"),
        )},
        "libraries": [],
        "limits": {
            "compile_timeout_s": 30,
            "run_timeout_s": 15,
            "inspect_timeout_s": 10,
            "repair_attempts": 2,
            "max_files": 40,
            "context_tokens": 4096,
            "output_tokens": 640,
        },
        "context": {
            "chars_per_token": 3.5,
            "sections": dict(DEFAULT_SECTIONS),
        },
        "commands": {key: list(value) for key, value in DEFAULT_COMMANDS.items()},
    }


def _fail(message: str) -> None:
    raise ProfileError(message)


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{where} precisa ser um objeto JSON.")
    return value


def _unknown_keys(value: Mapping[str, Any], allowed: frozenset[str] | set[str], where: str) -> None:
    unknown = sorted(set(value).difference(allowed))
    if unknown:
        _fail(
            f"Chave desconhecida em {where}: {', '.join(unknown)}. "
            f"Aceitas: {', '.join(sorted(allowed))}."
        )


def _integer(value: Any, where: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(f"{where} precisa ser inteiro.")
    if value < low or value > high:
        _fail(f"{where} precisa estar entre {low} e {high}; veio {value}.")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{where} precisa ser texto não vazio.")
    return value.strip()


def merge_profile(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Merge nested objects; lists and scalars replace the previous value."""
    result = dict(base)
    for key, value in override.items():
        current = result.get(key)
        if isinstance(value, dict) and isinstance(current, dict):
            result[key] = merge_profile(current, value)
        else:
            result[key] = value
    return result


def _validate(data: Mapping[str, Any], available_adapters: tuple[str, ...]) -> None:
    _unknown_keys(data, _TOP_KEYS, "perfil")

    version = data.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        _fail(f"schema_version precisa ser 1; veio {version!r}.")

    language = _mapping(data.get("language"), "language")
    _unknown_keys(language, {"id", "source_extension"}, "language")
    adapter_id = _text(language.get("id"), "language.id")
    if adapter_id not in available_adapters:
        _fail(
            f"Adaptador desconhecido: {adapter_id}. "
            f"Disponíveis: {', '.join(available_adapters) or '(nenhum)'}."
        )
    extension = _text(language.get("source_extension"), "language.source_extension")
    if not extension.startswith("."):
        _fail("language.source_extension precisa começar com ponto, por exemplo .java.")

    toolchain = _mapping(data.get("toolchain"), "toolchain")
    _unknown_keys(toolchain, set(_TOOLCHAIN_KEYS), "toolchain")
    for key in _TOOLCHAIN_KEYS:
        _text(toolchain.get(key), f"toolchain.{key}")

    libraries = data.get("libraries")
    if not isinstance(libraries, list):
        _fail("libraries precisa ser uma lista.")
    for index, item in enumerate(libraries):
        _text(item, f"libraries[{index}]")

    limits = _mapping(data.get("limits"), "limits")
    _unknown_keys(limits, set(_LIMIT_RANGES), "limits")
    for key, (low, high) in _LIMIT_RANGES.items():
        _integer(limits.get(key), f"limits.{key}", low, high)
    if limits["output_tokens"] >= limits["context_tokens"]:
        _fail(
            "limits.output_tokens precisa ser menor que limits.context_tokens "
            f"({limits['output_tokens']} >= {limits['context_tokens']})."
        )

    context = _mapping(data.get("context"), "context")
    _unknown_keys(context, {"chars_per_token", "sections"}, "context")
    ratio = context.get("chars_per_token")
    if isinstance(ratio, bool) or not isinstance(ratio, (int, float)):
        _fail("context.chars_per_token precisa ser numérico.")
    if ratio != ratio or ratio < 2.0 or ratio > 6.0:
        _fail(f"context.chars_per_token precisa estar entre 2.0 e 6.0; veio {ratio}.")
    sections = _mapping(context.get("sections"), "context.sections")
    _unknown_keys(sections, set(DEFAULT_SECTIONS), "context.sections")
    for name, value in sections.items():
        _integer(value, f"context.sections.{name}", 1, 8192)

    commands = _mapping(data.get("commands"), "commands")
    _unknown_keys(commands, set(COMMAND_IDS), "commands")
    seen: dict[str, str] = {}
    for command, aliases in commands.items():
        if not isinstance(aliases, list) or not aliases:
            _fail(f"commands.{command} precisa ser uma lista não vazia de aliases.")
        for alias in aliases:
            _text(alias, f"commands.{command}")
            folded = alias.strip().casefold()
            if folded in seen:
                _fail(
                    f"Alias duplicado: {alias!r} em {command} e {seen[folded]}."
                )
            seen[folded] = command
    if "exit" not in commands:
        _fail("commands.exit é obrigatório para garantir uma saída explícita.")


def _resolve_path(value: str, app_home: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else app_home / path


def _build(
    data: Mapping[str, Any],
    app_home: Path,
    *,
    origin: str,
    global_path: Path,
    project_path: Path | None,
) -> Profile:
    language = data["language"]
    sections = dict(DEFAULT_SECTIONS)
    sections.update(data["context"]["sections"])
    return Profile(
        language_id=language["id"].strip(),
        source_extension=language["source_extension"].strip(),
        toolchain=MappingProxyType(
            {
                key: _resolve_path(data["toolchain"][key].strip(), app_home)
                for key in _TOOLCHAIN_KEYS
            }
        ),
        libraries=tuple(
            _resolve_path(item.strip(), app_home) for item in data["libraries"]
        ),
        limits=Limits(**data["limits"]),
        context=ContextSettings(
            chars_per_token=float(data["context"]["chars_per_token"]),
            sections=MappingProxyType(sections),
        ),
        commands=MappingProxyType(
            {
                key: tuple(alias.strip() for alias in value)
                for key, value in data["commands"].items()
            }
        ),
        origin=origin,
        global_path=global_path,
        project_path=project_path,
    )


def default_profile(app_home: Path) -> Profile:
    data = _default_data()
    _validate(data, ("java8",))
    return _build(
        data,
        app_home,
        origin="global",
        global_path=app_home / "perfil.json",
        project_path=None,
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ProfileError(f"Não foi possível ler o perfil {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ProfileError(f"O perfil {path} não é JSON válido: {error}") from error
    return dict(_mapping(value, str(path)))


def load_profile(
    config: AppConfig,
    *,
    app_home: Path,
    available_adapters: tuple[str, ...],
) -> Profile:
    global_path = config.config_dir / "perfil.json"
    if not global_path.is_file():
        raise ProfileError(f"Perfil não encontrado: {global_path}")
    data = _load_json(global_path)

    project_path = config.project_root / ".assistente" / "perfil.json"
    if project_path.is_file():
        data = merge_profile(data, _load_json(project_path))
        origin = "project"
    else:
        project_path = None
        origin = "global"

    _validate(data, available_adapters)
    return _build(
        data,
        app_home,
        origin=origin,
        global_path=global_path,
        project_path=project_path,
    )


def ensure_profile(config: AppConfig, template: Path) -> Path:
    """Install the default profile once, preserving every later user edit."""
    config.config_dir.mkdir(parents=True, exist_ok=True)
    target = config.config_dir / "perfil.json"
    if target.exists():
        return target
    content = template.read_text(encoding="utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".perfil-", suffix=".tmp", dir=config.config_dir
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if target.exists():
            temporary.unlink(missing_ok=True)
        else:
            os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


def verify_paths(profile: Profile) -> None:
    """Check bundled paths at startup; the error names the path tested."""
    missing = [
        str(path)
        for path in (*profile.toolchain.values(), *profile.libraries)
        if not path.exists()
    ]
    if missing:
        raise ProfileError(
            "Arquivos do perfil não encontrados: " + "; ".join(missing)
        )
