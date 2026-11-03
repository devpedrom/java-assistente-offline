"""Honest separation between evidence, inference and local verification."""

from __future__ import annotations

from dataclasses import dataclass, field


def _section(title: str, items: list[str], empty: str = "Nenhuma evidência registrada.") -> str:
    body = "\n".join(f"- {item}" for item in items) if items else f"- {empty}"
    return f"## {title}\n{body}"


@dataclass
class EvidenceReport:
    confirmed_pdf: list[str] = field(default_factory=list)
    inferred_uml: list[str] = field(default_factory=list)
    compiled: list[str] = field(default_factory=list)
    locally_tested: list[str] = field(default_factory=list)
    unproven: list[str] = field(default_factory=list)
    context_omitted: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)

    def render(self) -> str:
        return "\n\n".join(
            (
                _section("Confirmado pelo PDF", self.confirmed_pdf),
                _section("Inferido do UML", self.inferred_uml),
                _section("Compilado", self.compiled),
                _section("Testado localmente", self.locally_tested),
                _section("Não comprovado", self.unproven),
                _section(
                    "Contexto omitido (limite de tokens)",
                    self.context_omitted,
                    "Nenhuma seção foi omitida.",
                ),
                _section(
                    "Observações de verificação",
                    self.observations,
                    "Nenhuma observação.",
                ),
            )
        )
