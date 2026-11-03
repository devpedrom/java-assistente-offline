from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.java.toolchain import JavaToolchain


class JavaTimeoutIntegrationTests(unittest.TestCase):
    def test_infinite_program_is_stopped_without_hanging_assistant(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Infinito.java").write_text(
                "public class Infinito { public static void main(String[] a) { while (true) {} } }\n",
                encoding="utf-8",
            )
            toolchain = JavaToolchain(root)
            compiled = toolchain.compile([Path("Infinito.java")])
            self.assertTrue(compiled.success, compiled.diagnostics)

            result = toolchain.run("Infinito", timeout_s=1)

        self.assertTrue(result.timed_out)
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
