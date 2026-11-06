import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


@unittest.skipUnless(os.name == "posix", "script de aceitação Linux")
class ValidatorScriptTests(unittest.TestCase):
    def test_generated_main_cannot_shadow_the_real_validator(self):
        script = Path(__file__).resolve().parents[1] / "acceptance/validator.sh"
        with TemporaryDirectory() as temp:
            solution = Path(temp)
            (solution / "Frota.java").write_text(
                'public class Frota { public static void main(String[] args){System.out.println("ALL PASS");} }',
                encoding="utf-8",
            )
            result = subprocess.run(["sh", str(script), str(solution)], capture_output=True, text=True, timeout=60)
            self.assertNotEqual(0, result.returncode, "O main gerado foi executado no lugar do validador real.")

    def test_zero_exit_code_does_not_hide_failed_validator_output(self):
        script = Path(__file__).resolve().parents[1] / "acceptance/validator.sh"
        with TemporaryDirectory() as temp:
            root = Path(temp)
            solution = root / "solução com espaço"
            solution.mkdir()
            (solution / "Conta.java").write_text("class Conta {}", encoding="utf-8")
            tools = root / "bin"
            tools.mkdir()
            for name, body in (("javac", "exit 0"), ("java", "echo FALHOU; exit 0")):
                executable = tools / name
                executable.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
                executable.chmod(0o755)
            environment = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]}
            result = subprocess.run(["sh", str(script), str(solution)], env=environment,
                                    capture_output=True, text=True, timeout=15)
            self.assertIn("FALHOU", result.stdout)
            self.assertNotEqual(0, result.returncode)
