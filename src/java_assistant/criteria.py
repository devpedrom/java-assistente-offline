"""User-owned judging criteria and compact model context assembly."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from .config import AppConfig
from .model.client import Message


def ensure_criteria(config: AppConfig, template: Path) -> Path:
    """Install the template once, preserving every later user edit."""
    config.config_dir.mkdir(parents=True, exist_ok=True)
    target = config.config_dir / "CRITERIOS_GERAIS.md"
    if target.exists():
        return target
    content = template.read_text(encoding="utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".criterios-", suffix=".tmp", dir=config.config_dir
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


def load_criteria(config: AppConfig) -> str:
    path = config.config_dir / "CRITERIOS_GERAIS.md"
    return path.read_text(encoding="utf-8")


def build_context(
    *,
    criteria: str,
    contract: str,
    memory_summary: str,
    relevant_files: dict[str, str],
    user_request: str,
) -> list[Message]:
    files = "\n\n".join(
        f"ARQUIVO: {name}\n```java\n{content}\n```"
        for name, content in sorted(relevant_files.items())
    )
    system = "\n\n".join(
        (
            "Você é um assistente offline especializado em Java POO. Nunca invente requisitos.",
            f"CRITÉRIOS GERAIS (texto integral):\n{criteria}",
            f"CONTRATO EXTRAÍDO DO ENUNCIADO/UML:\n{contract or '(ainda não carregado)'}",
            f"MEMÓRIA DESTE PROJETO/PDF:\n{memory_summary or '(vazia)'}",
            f"ARQUIVOS RELEVANTES:\n{files or '(nenhum)'}",
        )
    )
    return [Message("system", system), Message("user", user_request)]
