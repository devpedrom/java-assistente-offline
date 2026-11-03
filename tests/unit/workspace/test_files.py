import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.workspace.files import (
    PatchMismatchError,
    Workspace,
    WorkspacePathError,
)


class WorkspaceTests(unittest.TestCase):
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
