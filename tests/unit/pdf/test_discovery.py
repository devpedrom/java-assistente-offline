from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.pdf.discovery import discover_pdfs


class PdfDiscoveryTests(unittest.TestCase):
    def test_lists_only_root_pdfs_in_stable_alphabetical_order(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Zeta.PDF").touch()
            (root / "Árvore.pdf").touch()
            (root / "ignorar.txt").touch()
            (root / "subpasta").mkdir()
            (root / "subpasta" / "oculto.pdf").touch()

            result = discover_pdfs(root)

        self.assertEqual([item.name for item in result], ["Zeta.PDF", "Árvore.pdf"])


if __name__ == "__main__":
    unittest.main()
