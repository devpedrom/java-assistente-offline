from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.workspace.files import Workspace, PatchMismatchError
from java_assistant.workspace.history import History


class HistoryTests(unittest.TestCase):
    def test_undo_restores_exact_crlf_and_unicode_bytes(self):
        relative = Path("Conta.java")
        before = 'class Conta {\r\nString valor="😀";\r\n}\r\n'
        self.workspace.write(relative, before)
        self.history.record(self.workspace.write(relative, before.replace("valor", "nome")))
        self.assertTrue(self.history.undo_last().undone)
        self.assertEqual(before.encode("utf-8"), (self.root / relative).read_bytes())

    def test_newline_only_external_edit_blocks_undo(self):
        relative = Path("Conta.java")
        self.history.record(self.workspace.write(relative, "original\r\n"))
        (self.root / relative).write_bytes(b"original\n")
        self.assertFalse(self.history.undo_last().undone)
        self.assertEqual(b"original\n", (self.root / relative).read_bytes())

    def test_rejected_conditional_write_does_not_add_an_undo_entry(self):
        relative = Path("Conta.java")
        self.workspace.write(relative, "externo")
        with self.assertRaises(PatchMismatchError):
            self.history.write(relative, "gerado", expected="antigo")
        self.assertFalse(self.history.undo_last().undone)
        self.assertEqual(b"externo", (self.root / relative).read_bytes())

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.workspace = Workspace(self.root)
        self.history = History(self.workspace)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_undo_restores_previous_content(self) -> None:
        self.workspace.write(Path("Aluno.java"), "versão 1\n")
        change = self.workspace.write(Path("Aluno.java"), "versão 2\n")
        self.history.record(change)

        result = self.history.undo_last()

        self.assertTrue(result.undone)
        self.assertEqual(self.workspace.read(Path("Aluno.java")), "versão 1\n")

    def test_undo_deletes_file_created_by_assistant(self) -> None:
        change = self.workspace.write(Path("Novo.java"), "class Novo {}\n")
        self.history.record(change)

        result = self.history.undo_last()

        self.assertTrue(result.undone)
        self.assertFalse((self.root / "Novo.java").exists())

    def test_undo_refuses_to_overwrite_later_user_edit(self) -> None:
        change = self.workspace.write(Path("Seguro.java"), "gerado\n")
        self.history.record(change)
        (self.root / "Seguro.java").write_text("editado pelo usuário\n", encoding="utf-8")

        result = self.history.undo_last()

        self.assertFalse(result.undone)
        self.assertIn("alterado depois", result.reason)
        self.assertEqual((self.root / "Seguro.java").read_text(encoding="utf-8"), "editado pelo usuário\n")

    def test_empty_history_is_safe(self) -> None:
        result = self.history.undo_last()

        self.assertFalse(result.undone)
        self.assertIn("Nenhuma", result.reason)


if __name__ == "__main__":
    unittest.main()
