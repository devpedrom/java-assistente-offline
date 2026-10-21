from collections.abc import Callable
from pathlib import Path

from .config import AppConfig


InputFn = Callable[[str], str]


def run_cli(config: AppConfig, input_fn: InputFn = input) -> int:
    print(f"Assistente Java POO - projeto: {config.project_root}")
    while True:
        try:
            text = input_fn("> ").strip()
        except (EOFError, KeyboardInterrupt, StopIteration):
            return 0

        if text.casefold() in {"/sair", "sair"}:
            return 0
        if text:
            print("Modelo local ainda nao iniciado.")


def main() -> int:
    return run_cli(AppConfig.load(Path.cwd()))


if __name__ == "__main__":
    raise SystemExit(main())

