from pathlib import Path
import unittest

from java_assistant import session


class GenericRuleTests(unittest.TestCase):
    def test_product_mentions_no_exercise_specific_names(self):
        forbidden = ("Frota", "Veiculo", "Motocicleta", "Hatch", "Pickup",
                     "autonomia", "cilindrada", "bagageiro", "cambiao")
        root = Path(__file__).resolve().parents[2] / "src"
        for path in root.rglob("*.py"):
            for word in forbidden:
                with self.subTest(path=path, word=word):
                    self.assertNotIn(word, path.read_text(encoding="utf-8"))

    def test_percentage_and_fraction_rules_are_derived_from_text(self):
        for text, expected in (
            ("O volume aumenta em 25%", "base * 1.25"),
            ("aumento de 12,5%", "base * 1.125"),
            ("redução de 30%", "base * 0.7"),
            ("valor reduzido em 20%", "base * 0.8"),
            ("reduzida pela metade", "base * 0.5"),
            ("reduzido em um quarto", "base * 0.75"),
        ):
            with self.subTest(text=text):
                self.assertIn(expected, "\n".join(session._required_generation_rules(text)))

    def test_unrelated_text_does_not_create_arithmetic_rules(self):
        self.assertEqual((), session._required_generation_rules("CLASSE: Conta"))

    def test_generic_method_is_not_special_cased(self):
        requirements = "REGRAS ESPECÍFICAS DO PDF:\nConta\nVERIFICAÇÃO GERAL:"
        source = "public Double autonomia() { return super.autonomia() * 0.9; }"
        self.assertEqual((), session._semantic_issues(requirements, source))

    def test_equivalent_formula_is_not_rejected_by_multiplier_spelling(self):
        requirements = "O volume aumenta em 25%"
        self.assertEqual((), session._semantic_issues(requirements, "return base + base / 4.0;"))
