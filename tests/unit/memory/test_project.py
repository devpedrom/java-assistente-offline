from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from java_assistant.memory.project import ProjectMemory
from java_assistant.memory.store import ProjectStore, project_identifier
from java_assistant.uml.models import JavaClass, JavaContract


class ProjectMemoryTests(unittest.TestCase):
    def test_interrupted_requirements_update_cannot_restore_old_passing_evidence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            memory = ProjectMemory.open(root, root / "legado")
            contract = JavaContract((JavaClass("Conta", (), ()),), ())
            memory.select_requirements(contract, "class Conta", "texto", "texto-" + "a"*64)
            memory.record_verification(True, locally_tested=("Conta.total: aprovado",))
            with patch.object(memory.files, "save_verifications", side_effect=OSError("queda")):
                with self.assertRaises(OSError):
                    memory.select_requirements(contract, "class Conta\nregra nova", "texto", "texto-" + "b"*64)
            memory.cache.close()
            reopened = ProjectMemory.open(root, root / "legado")
            try:
                self.assertFalse(reopened.has_valid_compilation())
                self.assertEqual((), reopened.verifications.locally_tested)
            finally:
                reopened.close()

    def test_partial_compilation_does_not_verify_other_sources(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Good.java").write_text("class Good {}", encoding="utf-8")
            (root / "Broken.java").write_text("isto não compila", encoding="utf-8")
            memory = ProjectMemory.open(root, root / "legado")
            try:
                memory.record_verification(True, sources=[Path("Good.java")])
                self.assertEqual({"Good.java"}, set(memory.verifications.source_hashes))
                self.assertFalse(memory.has_valid_compilation())
            finally:
                memory.close()

    def test_rebuilds_cache_and_imports_legacy_only_once(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "projeto"
            root.mkdir()
            legacy = Path(temp) / "legado"
            store = ProjectStore.open("a"*64, project_identifier(root), legacy)
            store.remember("decision", "Usar herança")
            store.close()
            memory = ProjectMemory.open(root, legacy)
            self.assertEqual(1, memory.import_legacy("a"*64))
            self.assertEqual(0, memory.import_legacy("a"*64))
            memory.close()
            (root / ".assistente/memoria.db").write_bytes(b"corrompido")
            reopened = ProjectMemory.open(root, legacy)
            self.assertIn("Usar herança", reopened.summary())
            reopened.close()

    def test_external_edit_invalidates_only_affected_hashes_without_writing_sources(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ("Conta", "Outra"):
                (root / f"{name}.java").write_text(f"class {name} {{}}", encoding="utf-8")
            memory = ProjectMemory.open(root, root / "legado")
            memory.reconcile_sources()
            memory.record_verification(True, diagnostics="compilação aprovada")
            edited = "class Conta { int manual; }"
            (root / "Conta.java").write_text(edited, encoding="utf-8")
            changes = memory.reconcile_sources()
            self.assertEqual(("Conta.java",), changes.changed)
            snapshot = memory.load_verifications()
            self.assertNotIn("Conta.java", snapshot.source_hashes)
            self.assertIn("Outra.java", snapshot.source_hashes)
            self.assertFalse(snapshot.compiled)
            self.assertEqual(edited, (root / "Conta.java").read_text(encoding="utf-8"))
            self.assertLessEqual(len(memory.build_context("critérios", "Conta", max_chars=300)), 300)
            memory.close()

    def test_requirements_are_versioned_and_project_move_preserves_identity(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "origem"
            root.mkdir()
            memory = ProjectMemory.open(root, Path(temp) / "legado")
            identity = memory.manifest.project_id
            contract = JavaContract((JavaClass("Conta", (), ()),), ())
            memory.select_requirements(contract, "class Conta", "texto colado", "texto-" + "a"*64)
            memory.select_requirements(contract, "class Conta\nregra", "texto colado", "texto-" + "b"*64)
            self.assertEqual(2, memory.requirements.version)
            memory.close()
            moved = root.rename(Path(temp) / "destino")
            reopened = ProjectMemory.open(moved, Path(temp) / "legado")
            self.assertEqual(identity, reopened.manifest.project_id)
            self.assertEqual("class Conta\nregra", reopened.requirements.text)
            reopened.close()
