from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from .config import AppConfig
from .session import SessionReply


InputFn = Callable[[str], str]


class SessionLike(Protocol):
    def handle(self, text: str) -> SessionReply: ...


def run_cli(
    config: AppConfig,
    input_fn: InputFn = input,
    *,
    session: SessionLike | None = None,
) -> int:
    print(f"Assistente Java POO - projeto: {config.project_root}")
    while True:
        try:
            text = input_fn("> ").strip()
        except (EOFError, KeyboardInterrupt, StopIteration):
            return 0

        if session is None:
            if text.casefold() in {"/sair", "sair"}:
                return 0
            if text:
                print("Modelo local ainda não iniciado.")
            continue

        reply = session.handle(text)
        if reply.text:
            print(reply.text)
        if reply.exit_requested:
            return 0


def main() -> int:
    return run_cli(AppConfig.load(Path.cwd()))


if __name__ == "__main__":
    raise SystemExit(main())

