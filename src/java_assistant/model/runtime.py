from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import socket
import subprocess
import time
from typing import Protocol
from urllib.request import urlopen


class ProcessLike(Protocol):
    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...
    def kill(self) -> None: ...


class RuntimeStartError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    executable: Path
    model: Path
    context_size: int = 4096
    threads: int = 2
    ready_attempts: int = 240
    poll_interval: float = 0.25


def _free_port() -> int:
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        return int(server.getsockname()[1])


def _spawn(command: list[str]) -> ProcessLike:
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _is_ready(port: int) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=0.2) as response:
            return response.status == 200
    except OSError:
        return False


class LlamaRuntime:
    def __init__(
        self,
        config: RuntimeConfig,
        *,
        process_factory: Callable[[list[str]], ProcessLike] = _spawn,
        readiness_probe: Callable[[int], bool] = _is_ready,
        port_factory: Callable[[], int] = _free_port,
    ) -> None:
        self._config = config
        self._process_factory = process_factory
        self._readiness_probe = readiness_probe
        self._port_factory = port_factory
        self._process: ProcessLike | None = None
        self.port: int | None = None

    def start(self) -> None:
        if self._process is not None:
            return
        self.port = self._port_factory()
        command = [
            str(self._config.executable),
            "-m",
            str(self._config.model),
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--ctx-size",
            str(self._config.context_size),
            "--threads",
            str(self._config.threads),
            "--parallel",
            "1",
        ]
        self._process = self._process_factory(command)
        for _ in range(self._config.ready_attempts):
            if self._process.poll() is not None:
                break
            if self._readiness_probe(self.port):
                return
            time.sleep(self._config.poll_interval)
        self.stop()
        raise RuntimeStartError("O modelo local nao iniciou dentro do limite.")

    def stop(self) -> None:
        process, self._process = self._process, None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

