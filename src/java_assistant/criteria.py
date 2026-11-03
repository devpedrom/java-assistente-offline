"""User-owned judging criteria and compact model context assembly."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile

from .config import AppConfig
from .core.budget import ContextBudget, apply_budget
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


_PLACEHOLDERS = {
    "criteria": "",
    "pdf_excerpt": "(ainda não carregado)",
    "spec_target": "(ainda não carregado)",
    "memory": "(vazia)",
    "parents": "(nenhum)",
}
_LABELS = {
    "criteria": "CRITÉRIOS GERAIS (texto integral)",
    "pdf_excerpt": "TEXTO EXTRAÍDO DO PDF SELECIONADO",
    "spec_target": "CONTRATO EXTRAÍDO DO ENUNCIADO/UML",
    "memory": "MEMÓRIA DESTE PROJETO/PDF",
    "parents": "ARQUIVOS RELEVANTES",
}


def build_context(
    *,
    criteria: str,
    contract: str,
    source_text: str,
    memory_summary: str,
    relevant_files: dict[str, str],
    user_request: str,
    budget: ContextBudget | None = None,
) -> list[Message]:
    files = "\n\n".join(
        f"ARQUIVO: {name}\n```java\n{content}\n```"
        for name, content in sorted(relevant_files.items())
    )
    sections = {
        "criteria": criteria,
        "pdf_excerpt": source_text,
        "spec_target": contract,
        "memory": memory_summary,
        "parents": files,
        "user_request": user_request,
    }
    budgeted = apply_budget(sections, budget or ContextBudget())
    system_parts = ["Você é um assistente offline especializado em Java POO. Nunca invente requisitos."]
    for name in ("criteria", "pdf_excerpt", "spec_target", "memory", "parents"):
        if name not in budgeted.sections:
            continue
        text = budgeted.sections[name] or _PLACEHOLDERS[name]
        system_parts.append(f"{_LABELS[name]}:\n{text}")
    return [Message("system", "\n\n".join(system_parts)), Message("user", user_request)]
