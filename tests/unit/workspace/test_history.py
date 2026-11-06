from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from java_assistant.workspace.files import Workspace, PatchMismatchError
from java_assistant.workspace.history import History
from java_assistant.memory.files import CanonicalFiles


class HistoryTests(unittest.TestCase):
    def test_recovered_backup_allows_write_and_undo(self):
        files = CanonicalFiles.open(self.root)
        path = Path("Conta.java")
        self.workspace.write(path, "anterior")
        history = History(self.workspace, recovery=files)
        history.write(path, "novo")
        primary = files.path("recuperacao/alteracoes.json")
        files._write("recuperacao/alteracoes-anteriores.json", primary.read_text(encoding="utf-8"))
        primary.write_text("corrompido", encoding="utf-8")
        restored = History(self.workspace, recovery=files)
        restored.write(path, "terceiro")
        self.assertTrue(restored.undo_last().undone)
        self.assertEqual("novo", self.workspace.read(path))
        self.assertTrue(restored.undo_last().undone)
        self.assertEqual("anterior", self.workspace.read(path))

    def test_expected_content_and_crlf_are_preserved_on_method_write_and_undo(self):
        before = "class Conta {\r\nint total(){return 1;}\r\n}\r\n"
        after = before.replace("return 1", "return 2")
        path = Path("Conta.java")
        self.workspace.write(path, before)
        self.assertEqual(before, self.workspace.read(path))
        with self.assertRaises(PatchMismatchError):
            self.history.write(path, after, expected="conteúdo desatualizado")
        self.history.write(path, after, expected=before)
        self.assertEqual(after.encode(), (self.root / path).read_bytes())
        self.assertTrue(self.history.undo_last().undone)
        self.assertEqual(before.encode(), (self.root / path).read_bytes())

    def test_interruption_after_source_replace_keeps_before_content_recoverable(self):
        files = CanonicalFiles.open(self.root)
        self.workspace.write(Path("Conta.java"), "anterior")
        history = History(self.workspace, recovery=files)
        original_write = self.workspace.write
        def interrupted(path, text):
            original_write(path, text)
            raise KeyboardInterrupt()
        with patch.object(self.workspace, "write", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                history.write(Path("Conta.java"), "novo")
        restored = History(self.workspace, recovery=files)
        self.assertTrue(restored.undo_last().undone)
        self.assertEqual("anterior", self.workspace.read(Path("Conta.java")))

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

    def test_changes_show_a_unified_diff_without_treating_manual_edits_as_assistant_work(self):
        self.workspace.write(Path("Conta.java"), "saldo antigo\n")
        self.history.record(self.workspace.write(Path("Conta.java"), "saldo novo\n"))
        text = self.history.render_changes()
        self.assertIn("--- Conta.java", text)
        self.assertIn("+++ Conta.java", text)
        self.assertIn("-saldo antigo", text)
        self.assertIn("+saldo novo", text)
        self.workspace.write(Path("Conta.java"), "edição manual\n")
        self.assertNotIn("+edição manual", self.history.render_changes())
        self.assertIn("alterado depois", self.history.render_changes())


if __name__ == "__main__":
    unittest.main()
