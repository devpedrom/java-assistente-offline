import unittest

from java_assistant.pdf.extract import PdfEvidence
from java_assistant.uml.extract import UmlExtractor


class VariantTests(unittest.TestCase):
    def test_inferred_constructor_parameter_names_are_unique(self):
        contract = self.extract("class Raiz\n+ Raiz(arg2: int)\nclass Filho\n- arg2: int\nRaiz <|-- Filho")
        parameters = contract.classes[1].methods[-1].parameters
        self.assertEqual(2, len({name for name, _ in parameters}))

    def test_required_subclass_constructor_is_inferred_and_labelled(self):
        contract = self.extract("class Raiz\n# valor: Double\n+ Raiz(Double)\n"
                                "class Filho\n- ativo: boolean\nherda de: Raiz\n"
                                "class Neto\n- extra: int\nherda de: Filho")
        child, grandchild = contract.classes[1:]
        self.assertEqual(("Double", "boolean"), tuple(kind for _, kind in child.methods[-1].parameters))
        self.assertEqual(("Double", "boolean", "int"), tuple(kind for _, kind in grandchild.methods[-1].parameters))
        self.assertTrue(any("inferido" in warning.lower() and "Filho" in warning for warning in contract.warnings))

    def extract(self, text):
        return UmlExtractor().extract(PdfEvidence(text, "texto colado", ()))

    def test_reads_java_style_members_and_named_parameters(self):
        contract = self.extract(
            "CLASSE: Conta\nprivate Double saldo;\npublic Conta(Double saldo)\n"
            "public boolean sacar(double valor)"
        )
        account = contract.classes[0]
        self.assertEqual(("saldo", "Double", "private"),
                         (account.fields[0].name, account.fields[0].type_name, account.fields[0].visibility))
        self.assertEqual(("Conta", "Conta", (("saldo", "Double"),)),
                         (account.methods[0].name, account.methods[0].type_name, account.methods[0].parameters))
        self.assertEqual(("sacar", "boolean", (("valor", "double"),)),
                         (account.methods[1].name, account.methods[1].type_name, account.methods[1].parameters))

    def test_reads_class_heading_variants(self):
        for heading in ("CLASSE: Conta", "Classe Conta", "class Conta", "Conta:", "## Conta", "Conta"):
            with self.subTest(heading=heading):
                contract = self.extract(heading + "\n- saldo: double\n- sacar(valor: double): boolean")
                self.assertEqual(["Conta"], [item.name for item in contract.classes])
                self.assertEqual("saldo", contract.classes[0].fields[0].name)
                self.assertEqual("sacar", contract.classes[0].methods[0].name)
                self.assertEqual("private", contract.classes[0].methods[0].visibility)

    def test_empty_contract_carries_a_warning(self):
        contract = self.extract("texto sem diagrama nenhum")
        self.assertEqual((), contract.classes)
        self.assertTrue(contract.warnings)

    def test_uncertain_image_connector_allows_inheritance_confirmation(self):
        evidence = PdfEvidence("regras", "ocr", (), "class Raiz\nclass Filho\nRaiz -- Filho")
        contract = UmlExtractor().extract(evidence)
        self.assertIn("inheritance", contract.relationships[0].alternatives)

    def test_prose_heading_does_not_create_a_class(self):
        contract = self.extract("Regras:\nO saldo nunca deve ser negativo.")
        self.assertEqual((), contract.classes)
