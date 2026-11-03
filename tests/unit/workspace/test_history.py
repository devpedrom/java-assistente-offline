from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.workspace.files import Workspace
from java_assistant.workspace.history import History


class HistoryTests(unittest.TestCase):
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
