import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).parents[2]
INSTALLER = ROOT / "packaging" / "linux" / "instalar.sh"


def posix_shell() -> str | None:
    found = shutil.which("sh")
    if found:
        return found
    candidate = Path(r"C:\Program Files\Git\usr\bin\sh.exe")
    return str(candidate) if candidate.is_file() else None


def digest(path: Path) -> str:
    value = hashlib.sha256()
    value.update(path.read_bytes())
    return value.hexdigest()


def make_bundle(bundle: Path, version: str) -> None:
    payload = bundle / "payload"
    (payload / "bin").mkdir(parents=True)
    (payload / "share").mkdir()
    launcher = payload / "bin" / "java-assistente"
    launcher.write_text(f"#!/bin/sh\necho runtime-{version}\n", encoding="utf-8")
    launcher.chmod(0o755)
    (payload / "share" / "CRITERIOS_GERAIS.md").write_text(
        "CRITÉRIO PADRÃO\n", encoding="utf-8"
    )
    with tarfile.open(bundle / "runtime.tar.gz", "w:gz") as archive:
        archive.add(payload / "bin", arcname="bin")
        archive.add(payload / "share", arcname="share")
    (bundle / "model.gguf").write_bytes(b"GGUF-fake-model")
    manifest = bundle / "manifest.sha256"
    manifest.write_text(
        f"{digest(bundle / 'runtime.tar.gz')}  runtime.tar.gz\n"
        f"{digest(bundle / 'model.gguf')}  model.gguf\n",
        encoding="ascii",
    )
    shutil.copy2(INSTALLER, bundle / "instalar.sh")


class InstallerTests(unittest.TestCase):
    def test_all_linux_launchers_use_lf_and_have_shebang(self) -> None:
        scripts = [
            ROOT / "packaging" / "linux" / "instalar.sh",
            ROOT / "packaging" / "linux" / "build-bundle.sh",
            ROOT / "packaging" / "linux" / "desinstalar.sh",
            ROOT / "packaging" / "linux" / "java-assistente",
            ROOT / "tests" / "acceptance" / "run-offline.sh",
        ]
        for script in scripts:
            content = script.read_bytes()
            self.assertTrue(content.startswith(b"#!/bin/sh\n"), script)
            self.assertNotIn(b"\r\n", content, script)

    def test_installer_has_no_network_or_privileged_commands(self) -> None:
        script = INSTALLER.read_text(encoding="utf-8")
        for forbidden in ("sudo ", "curl ", "wget ", "apt ", "dnf "):
            self.assertNotIn(forbidden, script)
        self.assertIn("sha256sum -c", script)
        self.assertIn("JAVA_ASSISTANT_NO_START", script)
        self.assertIn('ORIGINAL_DIR=$(pwd -P)', script)
        self.assertIn('cd "$ORIGINAL_DIR"', script)
        builder = (ROOT / "packaging" / "linux" / "build-bundle.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('ARTIFACTS_DIR/python', builder)
        self.assertIn('ARTIFACTS_DIR/llama/llama-server', builder)
        self.assertIn('ARTIFACTS_DIR/native.tar.gz', builder)
        self.assertIn('assemble_runtime.py', builder)
        self.assertNotIn('mktemp -d', builder)
        assembler = (
            ROOT / "packaging" / "linux" / "assemble_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn('bin/pdftotext', assembler)
        self.assertIn('bin/javac', assembler)
        self.assertIn('lib/libgomp.so.1', assembler)
        runtime_launcher = (
            ROOT / "packaging" / "linux" / "java-assistente"
        ).read_text(encoding="utf-8")
        self.assertIn("LD_LIBRARY_PATH", runtime_launcher)
        self.assertIn("TESSDATA_PREFIX", runtime_launcher)

    @unittest.skipUnless(
        os.name != "nt" and posix_shell(),
        "execução do instalador reservada ao ambiente Linux",
    )
    def test_install_and_update_preserve_criteria_and_state(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = root / "bundle"
            bundle.mkdir()
            make_bundle(bundle, "v1")
            home = root / "home"
            data = root / "data"
            config = root / "config"
            state = root / "state"
            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": home.as_posix(),
                    "XDG_DATA_HOME": data.as_posix(),
                    "XDG_CONFIG_HOME": config.as_posix(),
                    "XDG_STATE_HOME": state.as_posix(),
                    "JAVA_ASSISTANT_NO_START": "1",
                }
            )

            first = subprocess.run(
                [posix_shell(), (bundle / "instalar.sh").as_posix()],
                cwd=bundle,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            criteria = config / "java-assistente" / "CRITERIOS_GERAIS.md"
            criteria.write_text("MINHA REGRA\n", encoding="utf-8")
            memory = state / "java-assistente" / "memoria.sqlite3"
            memory.parent.mkdir(parents=True, exist_ok=True)
            memory.write_text("preservar", encoding="utf-8")

            shutil.rmtree(bundle / "payload")
            make_bundle(bundle, "v2")
            second = subprocess.run(
                [posix_shell(), (bundle / "instalar.sh").as_posix()],
                cwd=bundle,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(criteria.read_text(encoding="utf-8"), "MINHA REGRA\n")
            self.assertEqual(memory.read_text(encoding="utf-8"), "preservar")
            self.assertTrue((home / ".local" / "bin" / "java-assistente").is_file())
            manifest_lines = (bundle / "manifest.sha256").read_text().splitlines()
            self.assertLessEqual(len(manifest_lines) + 2, 4)


if __name__ == "__main__":
    unittest.main()
