from pathlib import Path
import shutil
import unittest

from java_assistant.pdf.extract import PdfExtractor
from java_assistant.uml.extract import UmlExtractor
from tests.qualidade.medir import _load_expected, _shape


@unittest.skipUnless(all(shutil.which(tool) for tool in ("pdftotext", "pdftoppm", "tesseract")), "ferramentas PDF/OCR nativas indisponíveis")
class RealPdfTests(unittest.TestCase):
    def test_mixed_real_pdf_matches_full_contract_not_just_class_names(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures/frota/enunciado.pdf"
        evidence = PdfExtractor().extract(fixture)
        contract = UmlExtractor().extract(evidence)
        expected, scope = _load_expected("E5")
        self.assertEqual("full", scope)
        self.assertEqual(_shape(expected, scope), _shape(contract, scope))
        self.assertTrue(any("inferido" in warning for warning in contract.warnings))
