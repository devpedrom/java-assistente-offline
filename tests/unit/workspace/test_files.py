import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from java_assistant.workspace.files import (
    PatchMismatchError,
    Workspace,
    WorkspacePathError,
)


class WorkspaceTests(unittest.TestCase):
    def test_request_snapshot_does_not_open_existing_assistente_memory(self):
        memory = self.root / ".assistente" / "projeto.json"
        memory.parent.mkdir()
        memory.write_bytes(b"memoria antiga")
        relative = Path("Conta.java")
        self.workspace.write(relative, "class Conta {}\r\n")
        original_open = Path.open
        def without_memory(path, *args, **kwargs):
            if ".assistente" in path.relative_to(self.root).parts:
                raise AssertionError("Memória antiga não deve ser aberta")
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "open", new=without_memory):
            snapshot = self.workspace.snapshot()
            self.assertEqual("class Conta {}\r\n", self.workspace.expected_content(relative, snapshot))
            with self.assertRaises(WorkspacePathError):
                self.workspace.expected_content(Path(".assistente/projeto.json"), snapshot)
        self.assertEqual(b"memoria antiga", memory.read_bytes())

    def test_read_and_previous_content_preserve_utf8_and_crlf_bytes(self):
        relative = Path("Conta.java")
        before = 'class Conta {\r\nString texto = "😀";\r\n}\r\n'
        self.workspace.write(relative, before)
        self.assertEqual(before, self.workspace.read(relative))
        change = self.workspace.write(relative, before.replace("texto", "nome"))
        self.assertEqual(before, change.before_content)
        self.assertEqual(before.replace("texto", "nome").encode("utf-8"), (self.root / relative).read_bytes())

    def test_conditional_write_requires_expected_content_or_absence(self):
        relative = Path("Conta.java")
        self.workspace.write(relative, "primeiro", expected=None)
        for expected in (None, "desatualizado"):
            with self.subTest(expected=expected), self.assertRaises(PatchMismatchError):
                self.workspace.write(relative, "não gravar", expected=expected)
            self.assertEqual(b"primeiro", (self.root / relative).read_bytes())
        self.workspace.write(relative, "segundo", expected="primeiro")
        self.assertEqual(b"segundo", (self.root / relative).read_bytes())

    def test_external_edit_during_fsync_preserves_edit_and_removes_temporary(self):
        relative = Path("Conta.java")
        self.workspace.write(relative, "original")
        fsync = os.fsync
        def edited(descriptor):
            fsync(descriptor)
            (self.root / relative).write_bytes(b"externo")
        with patch("java_assistant.workspace.files.os.fsync", side_effect=edited):
            with self.assertRaises(PatchMismatchError):
                self.workspace.apply_patch(relative, "original", "gerado")
        self.assertEqual(b"externo", (self.root / relative).read_bytes())
        self.assertEqual([], list(self.root.rglob("*.tmp")))

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.workspace = Workspace(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_reads_and_atomically_writes_path_with_spaces_and_accents(self) -> None:
        change = self.workspace.write(Path("código fonte/Veículo.java"), "class Veículo {}\n")

        self.assertEqual(self.workspace.read(Path("código fonte/Veículo.java")), "class Veículo {}\n")
        self.assertFalse(change.existed_before)
        self.assertEqual(list(self.root.rglob("*.tmp")), [])

    def test_rejects_parent_traversal_and_absolute_path(self) -> None:
        with self.assertRaises(WorkspacePathError):
            self.workspace.write(Path("../fora.txt"), "não")
        with self.assertRaises(WorkspacePathError):
            self.workspace.read((self.root.parent / "fora.txt").resolve())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_rejects_symlink_that_escapes_root(self) -> None:
        with TemporaryDirectory() as outside_dir:
            link = self.root / "atalho"
            try:
                link.symlink_to(Path(outside_dir), target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink not permitted: {exc}")

            with self.assertRaises(WorkspacePathError):
                self.workspace.write(Path("atalho/fuga.txt"), "não")

    def test_crlf_content_hashes_the_same_after_reading_back(self) -> None:
        change = self.workspace.write(Path("Main.java"), "class Main {\r\n}\r\n")

        self.assertEqual(
            change.after_hash, self.workspace.current_hash(Path("Main.java"))
        )

    def test_apply_patch_requires_exact_expected_text(self) -> None:
        self.workspace.write(Path("Pessoa.java"), "class Pessoa {}\n")

        change = self.workspace.apply_patch(
            Path("Pessoa.java"),
            expected="class Pessoa {}\n",
            replacement="public class Pessoa {}\n",
        )
        self.assertEqual(self.workspace.read(Path("Pessoa.java")), "public class Pessoa {}\n")
        self.assertNotEqual(change.before_hash, change.after_hash)

        with self.assertRaises(PatchMismatchError):
            self.workspace.apply_patch(Path("Pessoa.java"), "texto antigo", "novo")


if __name__ == "__main__":
    unittest.main()
