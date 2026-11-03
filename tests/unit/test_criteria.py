from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.config import AppConfig
from java_assistant.criteria import build_context, ensure_criteria, load_criteria


class CriteriaTests(unittest.TestCase):
    def _config(self, root: Path) -> AppConfig:
        return AppConfig(root / "projeto", root / "dados", root / "config", root / "estado")

    def test_loads_complete_criteria_and_reinstall_does_not_overwrite_edit(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._config(root)
            template = root / "modelo.md"
            template.write_text("CRITÉRIO ORIGINAL\n", encoding="utf-8")
            path = ensure_criteria(config, template)
            path.write_text("MINHA REGRA ESPECÍFICA\nlinha 2\n", encoding="utf-8")

            ensure_criteria(config, template)

            self.assertEqual(load_criteria(config), "MINHA REGRA ESPECÍFICA\nlinha 2\n")

    def test_context_contains_full_criteria_contract_memory_and_relevant_files(self) -> None:
        messages = build_context(
            criteria="REGRA COMPLETA\nNÃO OMITIR",
            contract="Classe Pessoa com nome:String",
            source_text="A autonomia deve ser reduzida pela metade.",
            memory_summary="Getter deve retornar o campo",
            relevant_files={"Pessoa.java": "class Pessoa {}"},
            user_request="Corrija o getter",
        )

        joined = "\n".join(message.content for message in messages)
        self.assertIn("REGRA COMPLETA\nNÃO OMITIR", joined)
        self.assertIn("Classe Pessoa", joined)
        self.assertIn("reduzida pela metade", joined)
        self.assertIn("Getter deve", joined)
        self.assertIn("Pessoa.java", joined)
        self.assertEqual(messages[-1].content, "Corrija o getter")


if __name__ == "__main__":
    unittest.main()
