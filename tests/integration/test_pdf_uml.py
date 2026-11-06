from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest

from java_assistant.pdf.extract import PdfEvidence, PdfExtractionError, PdfExtractor
from java_assistant.uml.extract import UmlExtractor
from tests.unit.pdf.test_layout import diagram


UML_TEXT = """Diagrama de classes
class Veiculo
- placa: String
+ Veiculo(placa: String)
+ getPlaca(): String

class Carro
- portas: int
+ Carro(placa: String, portas: int)
+ getPortas(): int

Veiculo <|-- Carro
"""


def completed(args: list[str], stdout: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")


class FakeRunner:
    def __init__(self, text_layer: str = "", ocr_tsv: str = "") -> None:
        self.text_layer = text_layer
        self.ocr_tsv = ocr_tsv
        self.calls: list[list[str]] = []

    def __call__(self, args, **kwargs):
        command = [str(value) for value in args]
        self.calls.append(command)
        executable = Path(command[0]).name
        if executable.startswith("pdftotext"):
            Path(command[-1]).write_text(self.text_layer, encoding="utf-8")
            return completed(command)
        if executable.startswith("pdftoppm"):
            Path(command[-1] + "-1.png").touch()
            return completed(command)
        if executable.startswith("tesseract"):
            return completed(command, stdout=self.ocr_tsv)
        raise AssertionError(command)


def tsv_for(text: str) -> str:
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
    rows = [header]
    for line_number, line in enumerate(text.splitlines(), start=1):
        for word_number, word in enumerate(line.split(), start=1):
            rows.append(
                f"5\t1\t1\t1\t{line_number}\t{word_number}\t0\t0\t0\t0\t95\t{word}"
            )
    return "\n".join(rows)


class PdfUmlIntegrationTests(unittest.TestCase):
    def test_malformed_ocr_heading_cannot_attach_members_to_previous_class(self):
        text = "class Raiz\n- saldo: double\nclass Folha\n- taxa: double\nherda de: Raiz"
        ocr = "class Raiz\n- saldo: double\nclass Fol ha\n- taxa: double\nherda de: Raiz"
        expected = UmlExtractor().extract(PdfEvidence(text, "text", ()))
        actual = UmlExtractor().extract(PdfEvidence(text, "text+ocr", (), ocr))
        self.assertEqual(expected.classes, actual.classes)
        self.assertEqual(expected.relationships, actual.relationships)
        self.assertTrue(any("ilegível" in warning for warning in actual.warnings))

    def test_textual_and_visual_members_are_reconciled_without_duplicates(self):
        contract = UmlExtractor().extract(PdfEvidence(
            "class Conta\n- saldo: int\n+ total(): int", "text+ocr", (),
            "class Conta\n- saldo: int\n+ outro(): int"))
        self.assertEqual(1, len(contract.classes))
        self.assertEqual(["saldo"], [field.name for field in contract.classes[0].fields])
        self.assertEqual({"total", "outro"}, {method.name for method in contract.classes[0].methods})

    def test_conflicting_textual_and_visual_types_require_confirmation(self):
        with self.assertRaisesRegex(ValueError, "divergem"):
            UmlExtractor().extract(PdfEvidence("class Conta\n- saldo: int", "text+ocr", (),
                                               "class Conta\n- saldo: Double"))

    def test_textual_member_does_not_hide_image_only_classes(self):
        runner = self.layout_runner()
        runner.text_layer = "class Texto\n+ total(): int\nRegras: preserve o diagrama."
        with TemporaryDirectory() as temp:
            pdf = Path(temp) / "misto.pdf"
            pdf.touch()
            evidence = PdfExtractor(runner=runner).extract(pdf)
        contract = UmlExtractor().extract(evidence)
        self.assertTrue({"Texto", "Raiz", "FolhaA", "FolhaB"}.issubset({item.name for item in contract.classes}))
        self.assertIn("Regras:", evidence.text)
        self.assertIn("ocr", evidence.source)

    def layout_runner(self, partial=False):
        class LayoutRunner(FakeRunner):
            def __init__(self):
                super().__init__()
                self.crops = iter(("Raiz\n+ total(): Double", "" if partial else "FolhaA\n+ total(): Double",
                                   "" if partial else "FolhaB\n+ total(): Double"))
            def __call__(self, args, **kwargs):
                if Path(args[0]).name.startswith("pdftoppm"):
                    diagram(Path(str(args[-1]) + "-1.pgm"))
                    return completed(args)
                if Path(args[0]).name.startswith("tesseract"):
                    if "-classe-" in str(args[1]):
                        return completed(args, stdout=next(self.crops))
                    return completed(args, returncode=1)
                return super().__call__(args, **kwargs)
        return LayoutRunner()

    def test_complete_box_ocr_survives_failed_whole_page_ocr(self):
        with TemporaryDirectory() as temp:
            pdf = Path(temp) / "diagrama.pdf"
            pdf.touch()
            evidence = PdfExtractor(runner=self.layout_runner()).extract(pdf)
        contract = UmlExtractor().extract(evidence)
        self.assertEqual(["Raiz", "FolhaA", "FolhaB"], [item.name for item in contract.classes])
        self.assertTrue(any("textuais" in item for item in evidence.warnings))

    def test_partial_crop_ocr_is_explicitly_rejected_not_used_as_complete_contract(self):
        with TemporaryDirectory() as temp:
            pdf = Path(temp) / "diagrama.pdf"
            pdf.touch()
            with self.assertRaisesRegex(PdfExtractionError, "incompleto"):
                PdfExtractor(runner=self.layout_runner(partial=True)).extract(pdf)

    def test_nonempty_text_layer_does_not_hide_an_image_only_diagram(self):
        runner = FakeRunner(text_layer="Regras: preserve os nomes do diagrama.", ocr_tsv=tsv_for(UML_TEXT))
        with TemporaryDirectory() as temp:
            pdf = Path(temp) / "misto.pdf"
            pdf.touch()
            evidence = PdfExtractor(runner=runner).extract(pdf)
        contract = UmlExtractor().extract(evidence)
        self.assertEqual(["Veiculo", "Carro"], [item.name for item in contract.classes])
        self.assertIn("Regras:", evidence.text)
        self.assertIn("ocr", evidence.source)

    def test_portuguese_class_labels_and_herda_de_are_recognized(self) -> None:
        evidence = PdfEvidence(
            """CLASSE: Veiculo
# passageiros: int
+ autonomia(): Double
+ Veiculo(int, int, Double)

CLASSE: Motocicleta
Herda de: Veiculo
- cilindrada: int
+ autonomia(): Double

HIERARQUIA DE HERANÇA
LEGENDA UML
+ public (público)
# protected (protegido)
- private (privado)
""",
            "text",
            (),
        )

        contract = UmlExtractor().extract(evidence)

        self.assertEqual(
            [item.name for item in contract.classes],
            ["Veiculo", "Motocicleta"],
        )
        self.assertIn(
            ("Veiculo", "Motocicleta", "inheritance"),
            [
                (item.parent, item.child, item.kind)
                for item in contract.relationships
            ],
        )
        constructor = contract.classes[0].methods[1]
        self.assertEqual(
            [type_name for _, type_name in constructor.parameters],
            ["int", "int", "Double"],
        )
        self.assertEqual(
            [method.name for method in contract.classes[1].methods],
            ["autonomia", "Motocicleta"],
        )

    def test_text_pdf_produces_classes_members_and_inheritance(self) -> None:
        with TemporaryDirectory() as temp:
            pdf = Path(temp) / "enunciado com acento á.pdf"
            pdf.touch()
            evidence = PdfExtractor(runner=FakeRunner(text_layer=UML_TEXT)).extract(pdf)

        contract = UmlExtractor().extract(evidence)

        self.assertEqual(evidence.source, "text")
        self.assertEqual([item.name for item in contract.classes], ["Veiculo", "Carro"])
        self.assertEqual(contract.classes[0].fields[0].name, "placa")
        self.assertEqual(contract.classes[0].methods[0].name, "Veiculo")
        self.assertEqual(contract.relationships[0].kind, "inheritance")
        self.assertEqual(contract.relationships[0].parent, "Veiculo")
        self.assertEqual(contract.relationships[0].child, "Carro")
        self.assertGreaterEqual(contract.relationships[0].confidence, 0.9)

    def test_image_only_pdf_uses_ocr_and_keeps_explicit_source(self) -> None:
        runner = FakeRunner(ocr_tsv=tsv_for(UML_TEXT))
        with TemporaryDirectory() as temp:
            pdf = Path(temp) / "uml-imagem.pdf"
            pdf.touch()
            evidence = PdfExtractor(runner=runner).extract(pdf)

        contract = UmlExtractor().extract(evidence)

        self.assertEqual(evidence.source, "ocr")
        self.assertEqual([item.name for item in contract.classes], ["Veiculo", "Carro"])
        self.assertTrue(any(Path(call[0]).name.startswith("tesseract") for call in runner.calls))

    def test_empty_text_and_empty_ocr_is_an_error_not_false_success(self) -> None:
        with TemporaryDirectory() as temp:
            pdf = Path(temp) / "vazio.pdf"
            pdf.touch()
            with self.assertRaises(PdfExtractionError):
                PdfExtractor(runner=FakeRunner()).extract(pdf)

    def test_ambiguous_relationship_is_reported_with_alternatives(self) -> None:
        evidence = PdfEvidence(
            text="class Pedido\nclass Item\nPedido -- Item\n",
            source="text",
            warnings=(),
        )

        contract = UmlExtractor().extract(evidence)

        self.assertLess(contract.relationships[0].confidence, 0.9)
        self.assertEqual(
            contract.relationships[0].alternatives,
            ("association", "aggregation", "composition"),
        )


if __name__ == "__main__":
    unittest.main()
