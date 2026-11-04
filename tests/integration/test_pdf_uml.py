from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import unittest

from java_assistant.pdf.extract import PdfEvidence, PdfExtractionError, PdfExtractor
from java_assistant.uml.extract import UmlExtractor


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
            ["autonomia"],
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
