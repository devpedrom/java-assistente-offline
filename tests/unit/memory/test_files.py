from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from java_assistant.memory.files import CanonicalFiles
from java_assistant.memory.models import SessionState


class CanonicalFileTests(unittest.TestCase):
    def test_atomic_write_keeps_last_valid_state_and_recovers_invalid_json(self):
        with TemporaryDirectory() as temp:
            files = CanonicalFiles.open(Path(temp))
            state = SessionState(phase="compilar")
            files.save_state(state)
            with patch("java_assistant.memory.files.os.replace", side_effect=OSError("queda")):
                with self.assertRaises(OSError):
                    files.save_state(replace(state, phase="testar"))
            self.assertEqual(state, files.load_state())
            files.save_state(replace(state, phase="testar"))
            (Path(temp) / ".assistente/estado.json").write_text("{", encoding="utf-8")
            self.assertEqual(state, files.load_state())

    def test_identity_survives_move_and_last_truncated_event_is_recovered(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "origem"
            root.mkdir()
            files = CanonicalFiles.open(root)
            identity = files.load_manifest().project_id
            files.append_event({"kind": "decision", "content": "Usar composição"})
            with (root / ".assistente/decisoes.jsonl").open("ab") as handle:
                handle.write(b'{"kind":')
            moved = root.rename(Path(temp) / "destino")
            reopened = CanonicalFiles.open(moved)
            self.assertEqual(identity, reopened.load_manifest().project_id)
            self.assertEqual(1, len(reopened.recover()))

    def test_corruption_in_middle_is_reported(self):
        with TemporaryDirectory() as temp:
            files = CanonicalFiles.open(Path(temp))
            (Path(temp) / ".assistente/decisoes.jsonl").write_text('{bad}\n{}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                files.recover()

    def test_complete_final_event_without_newline_is_separated_before_append(self):
        with TemporaryDirectory() as temp:
            files = CanonicalFiles.open(Path(temp))
            (Path(temp) / ".assistente/decisoes.jsonl").write_text('{"kind":"decision","content":"primeiro"}', encoding="utf-8")
            files.recover()
            files.append_event({"kind": "decision", "content": "segundo"})
            self.assertEqual(2, len(files.recover()))

    def test_memory_symlink_escape_is_rejected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "projeto"
            root.mkdir()
            outside = Path(temp) / "fora"
            outside.mkdir()
            try:
                (root / ".assistente").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("symlink indisponível nesta plataforma")
            with self.assertRaises(ValueError):
                CanonicalFiles.open(root)
            self.assertEqual([], list(outside.iterdir()))
