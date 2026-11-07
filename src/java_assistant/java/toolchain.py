"""Shell-free adapter for the bundled Java toolchain."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import shutil
import subprocess
import tempfile
import re

from ..adapters.base import CompileResult, RunResult


class JavaToolchain:
    def __init__(
        self,
        project_root: Path,
        javac: Path | str = "javac",
        java: Path | str = "java",
        javap: Path | str = "javap",
        classpath: tuple[Path, ...] = (),
        inspect_timeout_s: int = 10,
    ) -> None:
        self.root = project_root.resolve(strict=True)
        self.javac = str(javac)
        self.java = str(java)
        self.javap = self._resolve_javap(javap)
        self.classpath = tuple(str(path) for path in classpath)
        self.inspect_timeout_s = inspect_timeout_s
        self._classes_dir: Path | None = None

    def classpath_args(self) -> tuple[str, ...]:
        if not self.classpath:
            return ()
        return ("-cp", os.pathsep.join(self.classpath))

    def _resolve_javap(self, requested: Path | str) -> str:
        value = str(requested)
        if value != "javap" or shutil.which(value):
            return value
        try:
            details = subprocess.run(
                [self.java, "-XshowSettings:properties", "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return value
        match = re.search(r"^\s*java\.home\s*=\s*(.+?)\s*$", details.stderr, re.MULTILINE)
        if not match:
            return value
        executable = "javap.exe" if os.name == "nt" else "javap"
        candidate = Path(match.group(1)) / "bin" / executable
        return str(candidate) if candidate.is_file() else value

    def _source(self, relative: Path) -> Path:
        value = Path(relative)
        if value.is_absolute():
            raise ValueError("A fonte Java precisa usar um caminho relativo ao projeto.")
        candidate = (self.root / value).resolve(strict=True)
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("A fonte Java precisa estar dentro do projeto.") from exc
        if not candidate.is_file() or candidate.suffix.casefold() != ".java":
            raise ValueError(f"Fonte Java inválida: {relative}")
        return candidate

    def compile(self, sources: list[Path], timeout_s: int = 30) -> CompileResult:
        if not sources:
            raise ValueError("Informe ao menos uma fonte Java.")
        resolved = [self._source(source) for source in sources]
        self.close()
        self._classes_dir = Path(tempfile.mkdtemp(prefix="java-assistente-classes-"))
        command = (
            self.javac,
            "-encoding",
            "UTF-8",
            *self.classpath_args(),
            "--release",
            "8",
            "-d",
            str(self._classes_dir),
            *(str(source) for source in resolved),
        )
        try:
            result = subprocess.run(
                command,
                cwd=self.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                check=False,
            )
            diagnostics = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
            return CompileResult(result.returncode == 0, diagnostics, self._classes_dir, command)
        except subprocess.TimeoutExpired as exc:
            return CompileResult(
                False,
                f"Compilação excedeu {timeout_s}s: {exc}",
                self._classes_dir,
                command,
            )

    def close(self) -> None:
        if self._classes_dir is not None:
            shutil.rmtree(self._classes_dir, ignore_errors=True)
            self._classes_dir = None

    def _popen_options(self) -> dict[str, object]:
        if os.name == "nt":
            return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        return {"start_new_session": True}

    def _stop_process_group(self, process: subprocess.Popen[str]) -> None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)

    def run(
        self,
        main_class: str,
        timeout_s: int,
        args: tuple[str, ...] = (),
        stdin: str = "",
        jvm_args: tuple[str, ...] = (),
    ) -> RunResult:
        if self._classes_dir is None:
            raise RuntimeError("Compile o projeto antes de executar.")
        if not main_class or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.$" for ch in main_class):
            raise ValueError("Nome de classe principal inválido.")
        command = [
            self.java,
            *jvm_args,
            "-cp",
            os.pathsep.join((str(self._classes_dir), *self.classpath, str(self.root))),
            main_class,
            *args,
        ]
        process = subprocess.Popen(
            command,
            cwd=self.root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **self._popen_options(),
        )
        try:
            stdout, stderr = process.communicate(stdin, timeout=timeout_s)
            return RunResult(process.returncode == 0, stdout, stderr, process.returncode, False)
        except subprocess.TimeoutExpired:
            self._stop_process_group(process)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate(timeout=5)
            return RunResult(False, stdout, stderr, process.returncode, True)

    def inspect(self, class_name: str, timeout_s: int | None = None) -> subprocess.CompletedProcess[str]:
        if self._classes_dir is None:
            raise RuntimeError("Compile o projeto antes de inspecionar classes.")
        return subprocess.run(
            [
                self.javap,
                "-private",
                "-classpath",
                os.pathsep.join((str(self._classes_dir), *self.classpath)),
                class_name,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.inspect_timeout_s if timeout_s is None else timeout_s,
            check=False,
        )
