from collections.abc import Callable
import os
from pathlib import Path
from typing import Protocol

from .adapters import adapter_ids, resolve_adapter
from .config import AppConfig
from .java.toolchain import JavaToolchain
from .model.client import LocalHttpTransport, ModelClient
from .model.runtime import LlamaRuntime, RuntimeConfig
from .pdf.extract import PdfExtractor
from .profile import ensure_profile, load_profile, verify_paths
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
            if text.casefold() == "/ajuda":
                print("Comandos: /pdf, /desfazer, /relatorio, /perfil, /ajuda e /sair.")
                continue
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
    session: AssistantSession | None = None
    runtime: LlamaRuntime | None = None
    try:
        ensure_profile(config, app_home / "share" / "perfil-padrao.json")
        profile = load_profile(
            config,
            app_home=app_home,
            available_adapters=adapter_ids(),
        )
        verify_paths(profile)
        runtime = LlamaRuntime(
            RuntimeConfig(
                executable=app_home / "tools" / "llama" / "llama-server",
                model=app_home / "model" / "model.gguf",
                context_size=profile.limits.context_tokens,
            )
        )
        runtime.start()
        assert runtime.port is not None
        session = AssistantSession(
            config=config,
            model=ModelClient(
                LocalHttpTransport(
                    runtime.port, max_tokens=profile.limits.output_tokens
                )
            ),
            pdf_extractor=PdfExtractor(
                pdftotext=app_home / "tools" / "native" / "bin" / "pdftotext",
                pdftoppm=app_home / "tools" / "native" / "bin" / "pdftoppm",
                tesseract=app_home / "tools" / "native" / "bin" / "tesseract",
                pdfimages=app_home / "tools" / "native" / "bin" / "pdfimages",
            ),
            toolchain=JavaToolchain(
                config.project_root,
                javac=profile.toolchain["compiler"],
                java=profile.toolchain["runtime"],
                javap=profile.toolchain["inspector"],
                classpath=profile.libraries,
                inspect_timeout_s=profile.limits.inspect_timeout_s,
            ),
            criteria_template=app_home / "share" / "CRITERIOS_GERAIS.md",
            profile=profile,
            adapter=resolve_adapter(profile.language_id),
        )
        return run_cli(config, session=session)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Não foi possível iniciar o assistente: {error}")
        return 2
    finally:
        if session is not None:
            session.close()
        if runtime is not None:
            runtime.stop()


if __name__ == "__main__":
    raise SystemExit(main())

