from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.config import AppConfig
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.session import AssistantSession
from tests.integration.test_session_flow import FixedExtractor, ScriptedModel


class SessionMemoryTests(unittest.TestCase):
    def test_undo_survives_restart_and_invalidates_report_evidence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            original = "public class Conta { public int total(){return 1;} }"
            first = self.make_session(root, ScriptedModel(["{return 2;}"]))
            path = first.config.project_root / "Conta.java"
            path.write_text(original, encoding="utf-8")
            first.handle("/enunciado")
            first.handle("class Conta\n+ total(): int")
            first.handle("/fim")
            first.handle("corrija somente Conta")
            first.close()
            second = self.make_session(root)
            try:
                self.assertTrue(second.evidence.compiled)
                self.assertIn("desfeita", second.handle("/desfazer").text)
                self.assertEqual(original, path.read_text(encoding="utf-8"))
                self.assertEqual([], second.evidence.compiled)
                self.assertEqual([], second.evidence.locally_tested)
                self.assertFalse(second.memory.has_valid_compilation())
            finally:
                second.close()

    def test_undo_immediately_invalidates_in_memory_report(self):
        with TemporaryDirectory() as temp:
            first = self.make_session(Path(temp), ScriptedModel(["public class Conta {} "]))
            try:
                first.handle("/enunciado")
                first.handle("class Conta")
                first.handle("/fim")
                first.handle("Resolva")
                self.assertTrue(first.evidence.compiled)
                first.handle("/desfazer")
                self.assertEqual([], first.evidence.compiled)
            finally:
                first.close()

    def make_session(self, root, model=None, extractor=None):
        project = root / "projeto"
        project.mkdir(exist_ok=True)
        template = root / "criterios.md"
        template.write_text("Java POO.", encoding="utf-8")
        return AssistantSession(config=AppConfig(project, root / "data", root / "config", root / "state"),
            model=model or ScriptedModel([]), pdf_extractor=extractor or FixedExtractor(""),
            toolchain=JavaToolchain(project), criteria_template=template)

    def test_two_sessions_restore_text_contract_without_calling_model(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.make_session(root, ScriptedModel(["public class Conta { public int total(){return 2;} }"]))
            first.handle("/enunciado")
            first.handle("class Conta\n+ total(): int")
            first.handle("/fim")
            first.handle("Resolva")
            identity = first.memory.manifest.project_id
            first.close()
            second = self.make_session(root)
            try:
                self.assertIn("Projeto retomado", second.resume_message)
                self.assertIn("Conta", second.resume_message)
                self.assertEqual(identity, second.memory.manifest.project_id)
                self.assertIn("total(): int", second.handle("/contrato").text)
                self.assertIn("Fase", second.handle("/estado").text)
                self.assertTrue(second.memory.has_valid_compilation())
                reply = second.handle("Resolva")
                self.assertIn("compilação Java 8 aprovada", reply.text)
                self.assertEqual(0, second.model.calls)
                second.close()
            finally:
                second.close()

    def test_pdf_change_and_external_source_edit_invalidate_old_evidence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.make_session(root, extractor=FixedExtractor("class Conta"))
            pdf = first.config.project_root / "enunciado.pdf"
            pdf.write_bytes(b"original")
            first.handle("/pdf")
            first.handle("1")
            first.memory.record_verification(True)
            first.close()
            pdf.write_bytes(b"modificado")
            second = self.make_session(root)
            try:
                self.assertIn("PDF mudou", second.resume_message)
                self.assertIsNone(second._contract)
                self.assertFalse(second.memory.has_valid_compilation())
            finally:
                second.close()

    def test_model_cannot_overwrite_canonical_memory(self):
        with TemporaryDirectory() as temp:
            session = self.make_session(Path(temp), ScriptedModel([
                '<write_file path=".assistente/projeto.json">{}</write_file>', '<respond>fim</respond>'
            ]))
            try:
                identity = session.memory.manifest.project_id
                session.handle("grave um arquivo")
                self.assertEqual(identity, session.memory.files.load_manifest().project_id)
            finally:
                session.close()

    def test_criteria_changes_invalidate_evidence_during_an_open_session(self):
        with TemporaryDirectory() as temp:
            session = self.make_session(Path(temp))
            try:
                session.handle("/enunciado")
                session.handle("class Conta")
                session.handle("/fim")
                session.memory.record_verification(True)
                (Path(temp) / "config/CRITERIOS_GERAIS.md").write_text("Novos critérios", encoding="utf-8")
                session.handle("/estado")
                self.assertFalse(session.memory.has_valid_compilation())
            finally:
                session.close()

    def test_active_pdf_change_blocks_generation_and_old_evidence(self):
        with TemporaryDirectory() as temp:
            session = self.make_session(Path(temp), extractor=FixedExtractor("class Conta"))
            try:
                pdf = session.config.project_root / "enunciado.pdf"
                pdf.write_bytes(b"original")
                session.handle("/pdf")
                session.handle("1")
                session.memory.record_verification(True)
                pdf.write_bytes(b"alterado")
                self.assertIn("PDF mudou", session.handle("/estado").text)
                self.assertIsNone(session._contract)
                self.assertFalse(session.memory.has_valid_compilation())
                self.assertIn("/pdf", session.handle("Resolva").text)
                self.assertEqual(0, session.model.calls)
            finally:
                session.close()
