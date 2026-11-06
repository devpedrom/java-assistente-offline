from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from java_assistant.java.toolchain import JavaToolchain
from java_assistant.java import methods
from java_assistant.java.validator import ContractValidator
from java_assistant.uml.models import JavaClass, JavaContract, JavaMember
from java_assistant.workspace.files import Workspace, PatchMismatchError


SOURCE = '''public class Conta {
    private String marcador = "😀";
    public Conta(int saldo) { }
    public Double total(int x) { String fim = "}"; /* { */ return 1.0; }
    public Double total(double x) { return 2.0; }
    class Interna { public int total() { return 999; } }
}
'''

CONTRACT = JavaContract((JavaClass("Conta", (JavaMember("marcador", "String", "private"),), (
    JavaMember("Conta", "Conta", "public", (("saldo", "int"),)),
    JavaMember("total", "Double", "public", (("x", "int"),)),
    JavaMember("total", "Double", "public", (("x", "double"),)),
)),), ())


class MethodTests(unittest.TestCase):
    def test_body_candidate_is_validated_without_writing_original_or_other_members(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "Conta.java"
            path.write_bytes(SOURCE.encode("utf-8"))
            toolchain = JavaToolchain(root)
            method = methods.locate_methods(toolchain, Path("Conta.java"), "Conta")[0]
            body = methods.extract_body("```java\n{ return 4.0; }\n```")
            candidate = methods.validate_method(Workspace(root), toolchain, CONTRACT, Path("Conta.java"), method, body, SOURCE)
            self.assertEqual(SOURCE.replace('{ String fim = "}"; /* { */ return 1.0; }', body, 1), candidate)
            self.assertEqual(SOURCE.encode("utf-8"), path.read_bytes())
            self.assertEqual(["Conta.java"], [p.name for p in root.iterdir()])

    def test_member_injection_and_invalid_java_preserve_original(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "Conta.java"
            path.write_bytes(SOURCE.encode("utf-8"))
            toolchain = JavaToolchain(root)
            method = methods.locate_methods(toolchain, Path("Conta.java"), "Conta")[0]
            for body in ("{ return naoExiste; }", "{ return 3.0; } public int injetado(){return 4;}"):
                with self.subTest(body=body), self.assertRaises(ValueError):
                    methods.validate_method(Workspace(root), toolchain, CONTRACT, Path("Conta.java"), method, body, SOURCE)
            self.assertEqual(SOURCE.encode("utf-8"), path.read_bytes())

    def test_external_edit_during_validation_is_preserved(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "Conta.java"
            path.write_bytes(SOURCE.encode("utf-8"))
            toolchain = JavaToolchain(root)
            method = methods.locate_methods(toolchain, Path("Conta.java"), "Conta")[0]
            validate = ContractValidator.validate
            def edited(validator, contract, staging):
                result = validate(validator, contract, staging)
                path.write_text("edição externa", encoding="utf-8")
                return result
            with patch.object(ContractValidator, "validate", new=edited), self.assertRaises(PatchMismatchError):
                methods.validate_method(Workspace(root), toolchain, CONTRACT, Path("Conta.java"), method, "{return 4.0;}", SOURCE)
            self.assertEqual("edição externa", path.read_text(encoding="utf-8"))

    def test_jdk_positions_preserve_unicode_and_identify_only_owner_overloads(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Conta.java").write_bytes(SOURCE.encode("utf-8"))
            toolchain = JavaToolchain(root)
            found = methods.locate_methods(toolchain, Path("Conta.java"), "Conta")
            self.assertEqual([("total", ("int",)), ("total", ("double",))],
                             [(item.name, item.parameter_types) for item in found])
            self.assertEqual('{ String fim = "}"; /* { */ return 1.0; }', SOURCE[found[0].start:found[0].end])
            self.assertEqual('{ return 2.0; }', SOURCE[found[1].start:found[1].end])
            self.assertIn("total(int x)", found[0].signature)
            self.assertEqual(["Conta.java"], [path.name for path in root.iterdir()])

    def test_offsets_use_actual_crlf_bytes_without_normalizing_the_source(self):
        source = 'public class Conta {\r\n' + '\r\n'*20 + 'public int total(){return 1;}\r\n}'
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Conta.java").write_bytes(source.encode("utf-8"))
            found = methods.locate_methods(JavaToolchain(root), Path("Conta.java"), "Conta")
            self.assertEqual("{return 1;}", source[found[0].start:found[0].end])

    def test_method_lookup_rejects_absolute_and_parent_paths(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "Conta.java"
            path.write_text(SOURCE, encoding="utf-8")
            toolchain = JavaToolchain(root)
            for invalid in (path.resolve(), Path("sub/../Conta.java")):
                with self.subTest(path=invalid), self.assertRaises(ValueError):
                    methods.locate_methods(toolchain, invalid, "Conta")
