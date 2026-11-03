"""Command aliases declared by the profile, without behaviour changes."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from ..profile import COMMAND_IDS


_HELP_ORDER = COMMAND_IDS


@dataclass(frozen=True)
class CommandRegistry:
    aliases: Mapping[str, str]

    @classmethod
    def from_profile(
        cls, commands: Mapping[str, tuple[str, ...]]
    ) -> "CommandRegistry":
        aliases: dict[str, str] = {}
        for command, names in commands.items():
            if command not in COMMAND_IDS:
                raise ValueError(f"Comando desconhecido no perfil: {command!r}.")
            if not names:
                raise ValueError(
                    f"O comando {command!r} precisa de ao menos um alias."
                )
            for alias in names:
                folded = alias.strip().casefold()
                if not folded:
                    raise ValueError(f"Alias vazio no comando {command!r}.")
                if folded in aliases:
                    raise ValueError(
                        f"Alias duplicado: {alias!r} em {command!r} e "
                        f"{aliases[folded]!r}."
                    )
                aliases[folded] = command
        if "exit" not in commands:
            raise ValueError("O comando exit é obrigatório.")
        return cls(MappingProxyType(aliases))

    def resolve(self, text: str) -> str | None:
        return self.aliases.get(text.strip().casefold())

    def help_text(self) -> str:
        active = [
            alias
            for command in _HELP_ORDER
            for alias, value in self.aliases.items()
            if value == command
        ]
        return "Comandos: " + ", ".join(active) + "."


__all__ = ["CommandRegistry"]
