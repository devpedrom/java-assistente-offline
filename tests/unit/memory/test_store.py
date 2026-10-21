from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.memory.store import ProjectStore


class ProjectStoreTests(unittest.TestCase):
    def test_persists_events_after_reopen_and_isolates_pdf(self) -> None:
        with TemporaryDirectory() as temp:
            state = Path(temp)
            first = ProjectStore.open("pdf-a", "projeto", state)
            first.remember("decision", "Usar composição em Pedido-Itens")
            first.close()

            reopened = ProjectStore.open("pdf-a", "projeto", state)
            other_pdf = ProjectStore.open("pdf-b", "projeto", state)

            self.assertIn("composição", reopened.summary())
            self.assertNotIn("composição", other_pdf.summary())
            reopened.close()
            other_pdf.close()

    def test_summary_is_compact_and_keeps_newest_information(self) -> None:
        with TemporaryDirectory() as temp:
            store = ProjectStore.open("pdf", "projeto", Path(temp))
            for number in range(20):
                store.remember("adjustment", f"ajuste-{number}-" + ("x" * 40))

            summary = store.summary(max_chars=180)

            self.assertLessEqual(len(summary), 180)
            self.assertIn("ajuste-19", summary)
            store.close()


if __name__ == "__main__":
    unittest.main()
