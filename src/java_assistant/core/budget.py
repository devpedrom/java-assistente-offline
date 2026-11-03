"""Token budget for the model context, with explicit priority and truncation."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Mapping

from ..profile import DEFAULT_SECTIONS


PROTECTED_SECTIONS = frozenset({"protocol", "criteria", "spec_target", "user_request"})
DROP_ORDER = ("memory", "pdf_excerpt", "parents", "rules")


class ContextBudgetError(ValueError):
    """Raised when the context cannot fit even after dropping sections."""


@dataclass(frozen=True)
class ContextBudget:
    context_tokens: int = 4096
    output_tokens: int = 640
    chars_per_token: float = 3.5
    sections: Mapping[str, int] = field(default=DEFAULT_SECTIONS)
    reserved_tokens: int = 128


@dataclass(frozen=True)
class BudgetedContext:
    sections: Mapping[str, str]
    omitted: tuple[str, ...]
    truncated: tuple[str, ...]
    available_tokens: int


def _cap_chars(tokens: int, chars_per_token: float) -> int:
    return max(1, int(tokens * chars_per_token))


def _truncate(text: str, cap: int) -> str:
    cut = text.rfind("\n", 0, cap)
    if cut <= 0:
        cut = cap
    kept = text[:cut].rstrip()
    omitted = len(text) - len(kept)
    return kept + f"\n[... truncado: {omitted} caracteres omitidos]"


def apply_budget(
    sections: Mapping[str, str], budget: ContextBudget
) -> BudgetedContext:
    available = budget.context_tokens - budget.output_tokens - budget.reserved_tokens
    if available <= 0:
        raise ContextBudgetError(
            "O orçamento de contexto não deixa tokens para a entrada; "
            "aumente context_tokens ou reduza output_tokens no perfil."
        )

    kept = dict(sections)
    ceilings = dict(budget.sections)
    # Essential input may borrow space from optional sections, never silently
    # lose a signature or a confirmed rule to a per-section ceiling.
    for name in ("spec_target", "user_request"):
        if name in kept:
            needed = math.ceil(len(kept[name]) / budget.chars_per_token)
            ceilings[name] = max(ceilings.get(name, 0), needed)
    total = sum(ceilings.get(name, 0) for name in kept)
    omitted: list[str] = []
    for name in DROP_ORDER:
        if total <= available:
            break
        if name in kept and name not in PROTECTED_SECTIONS:
            total -= ceilings.get(name, 0)
            del kept[name]
            omitted.append(name)
    if total > available:
        raise ContextBudgetError(
            "As seções obrigatórias do contexto excedem o orçamento de "
            f"{available} tokens; aumente context_tokens ou reduza output_tokens "
            "no perfil."
        )

    result: dict[str, str] = {}
    truncated: list[str] = []
    for name, text in kept.items():
        ceiling = ceilings.get(name)
        if ceiling is None:
            if name == "criteria":
                raise ContextBudgetError(
                    "Os critérios gerais não têm teto no orçamento configurado. "
                    "Defina context.sections.criteria no perfil."
                )
            result[name] = text
            continue
        cap = _cap_chars(ceiling, budget.chars_per_token)
        if name == "user_request" and len(text) > _cap_chars(
            budget.sections.get(name, ceiling), budget.chars_per_token
        ):
            truncated.append(name)
        if len(text) <= cap:
            result[name] = text
            continue
        if name == "criteria":
            raise ContextBudgetError(
                "Os critérios gerais excedem o limite de "
                f"{ceiling} tokens (~{cap} caracteres). Reduza o arquivo "
                "CRITERIOS_GERAIS.md para caber no orçamento de contexto."
            )
        if name == "user_request":
            result[name] = text
            truncated.append(name)
            continue
        result[name] = _truncate(text, cap)
        truncated.append(name)

    return BudgetedContext(
        sections=MappingProxyType(result),
        omitted=tuple(omitted),
        truncated=tuple(truncated),
        available_tokens=available,
    )
