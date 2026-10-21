from collections.abc import Callable
import os
from pathlib import Path
from typing import Protocol

from .config import AppConfig
from .java.toolchain import JavaToolchain
from .model.client import LocalHttpTransport, ModelClient
from .model.runtime import LlamaRuntime, RuntimeConfig
from .pdf.extract import PdfExtractor
from .session import SessionReply
from .session import AssistantSession


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
    config = AppConfig.load(Path.cwd())
    app_home_value = os.environ.get("JAVA_ASSISTANT_HOME")
    if not app_home_value:
        print("Instalação incompleta: JAVA_ASSISTANT_HOME não foi definido.")
        return 2
    app_home = Path(app_home_value).resolve()
    runtime = LlamaRuntime(
        RuntimeConfig(
            executable=app_home / "bin" / "llama-server",
            model=app_home / "model" / "model.gguf",
        )
    )
    session: AssistantSession | None = None
    try:
        runtime.start()
        assert runtime.port is not None
        session = AssistantSession(
            config=config,
            model=ModelClient(LocalHttpTransport(runtime.port)),
            pdf_extractor=PdfExtractor(
                pdftotext=app_home / "tools" / "poppler" / "bin" / "pdftotext",
                pdftoppm=app_home / "tools" / "poppler" / "bin" / "pdftoppm",
                tesseract=app_home / "tools" / "tesseract" / "bin" / "tesseract",
            ),
            toolchain=JavaToolchain(
                config.project_root,
                javac=app_home / "tools" / "jdk" / "bin" / "javac",
                java=app_home / "tools" / "jdk" / "bin" / "java",
                javap=app_home / "tools" / "jdk" / "bin" / "javap",
            ),
            criteria_template=app_home / "share" / "CRITERIOS_GERAIS.md",
        )
        return run_cli(config, session=session)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Não foi possível iniciar o assistente: {error}")
        return 2
    finally:
        if session is not None:
            session.close()
        runtime.stop()


if __name__ == "__main__":
    raise SystemExit(main())

