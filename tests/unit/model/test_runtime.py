from pathlib import Path
import unittest

from java_assistant.model.runtime import LlamaRuntime, RuntimeConfig, RuntimeStartError


class FakeProcess:
    def __init__(self, return_code: int | None = None) -> None:
        self.return_code = return_code
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.return_code

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        if self.return_code is None:
            self.return_code = 0
        return self.return_code

    def kill(self) -> None:
        self.killed = True
        self.return_code = -9


class RuntimeTests(unittest.TestCase):
    def test_start_binds_server_to_loopback_with_conservative_limits(self) -> None:
        calls: list[list[str]] = []
        process = FakeProcess()

        def process_factory(command: list[str]) -> FakeProcess:
            calls.append(command)
            return process

        config = RuntimeConfig(Path("llama-server"), Path("model.gguf"), threads=2)
        self.assertGreaterEqual(
            config.ready_attempts * config.poll_interval,
            45,
            "um modelo maior precisa de pelo menos 45 s para iniciar em CPU fraca",
        )
        runtime = LlamaRuntime(
            config,
            process_factory=process_factory,
            readiness_probe=lambda _port: True,
            port_factory=lambda: 43123,
        )

        runtime.start()

        self.assertEqual(43123, runtime.port)
        self.assertEqual(
            ["llama-server", "-m", "model.gguf", "--host", "127.0.0.1", "--port", "43123", "--ctx-size", "4096", "--threads", "2", "--parallel", "1"],
            calls[0],
        )

    def test_start_timeout_stops_process(self) -> None:
        process = FakeProcess()
        config = RuntimeConfig(Path("llama-server"), Path("model.gguf"), ready_attempts=2, poll_interval=0)
        runtime = LlamaRuntime(
            config,
            process_factory=lambda _command: process,
            readiness_probe=lambda _port: False,
            port_factory=lambda: 43123,
        )

        with self.assertRaises(RuntimeStartError):
            runtime.start()

        self.assertTrue(process.terminated)

    def test_stop_terminates_running_process(self) -> None:
        process = FakeProcess()
        runtime = LlamaRuntime(
            RuntimeConfig(Path("llama-server"), Path("model.gguf")),
            process_factory=lambda _command: process,
            readiness_probe=lambda _port: True,
            port_factory=lambda: 43123,
        )
        runtime.start()

        runtime.stop()

        self.assertTrue(process.terminated)


if __name__ == "__main__":
    unittest.main()

