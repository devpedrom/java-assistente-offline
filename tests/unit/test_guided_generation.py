import unittest

from java_assistant.session import (
    _diagnostic_guidance,
    _extract_java_source,
    _semantic_issues,
)


class GuidedGenerationTests(unittest.TestCase):
    def test_extracts_plain_or_fenced_single_class_source(self) -> None:
        plain = "public class Veiculo {}"
        fenced = "```java\npublic class Veiculo {}\n```"

        self.assertEqual(plain + "\n", _extract_java_source(plain, "Veiculo"))
        self.assertEqual(plain + "\n", _extract_java_source(fenced, "Veiculo"))

    def test_extracts_first_write_block_even_if_model_added_more_actions(self) -> None:
        reply = (
            '<write_file path="Veiculo.java">\npublic class Veiculo {}\n</write_file>\n'
            "<compile_java />"
        )

        self.assertEqual(
            "public class Veiculo {}\n", _extract_java_source(reply, "Veiculo")
        )

    def test_rejects_wrong_or_multiple_public_classes(self) -> None:
        with self.assertRaises(ValueError):
            _extract_java_source("public class Carro {}", "Veiculo")
        with self.assertRaises(ValueError):
            _extract_java_source(
                "public class Veiculo {}\npublic class Carro {}", "Veiculo"
            )

    def test_semantic_checks_reject_wrong_percentage_and_duplicate_parent_effect(self) -> None:
        requirements = """REGRAS ESPECÍFICAS DO PDF:
HATCH:
calculaVolume aumenta em 100% ou em 50%.
VERIFICAÇÃO GERAL: não aplique duas vezes efeito de super.
"""
        wrong = """public class Hatch extends Carro {
public Double autonomia() { return super.autonomia() * 0.9; }
public Double calculaVolume(int passageiros) { return bagageiro * 1.1; }
}"""
        correct = """public class Hatch extends Carro {
public Double autonomia() { return super.autonomia(); }
public Double calculaVolume(int passageiros) {
if (passageiros < 3) return bagageiro * 2.0;
if (passageiros == 3) return bagageiro * 1.5;
return (double) bagageiro;
}
}"""

        self.assertTrue(_semantic_issues(requirements, wrong))
        self.assertEqual((), _semantic_issues(requirements, correct))

    def test_semantic_checks_distinguish_quarter_from_remaining_three_quarters(self) -> None:
        requirements = "reduzida em um quarto quando houver carga"

        self.assertTrue(_semantic_issues(requirements, "return base * 0.25;"))
        self.assertEqual((), _semantic_issues(requirements, "return base * 0.75;"))

    def test_semantic_checks_require_explicit_never_greater_invariant(self) -> None:
        requirements = "O peso da carga nunca pode ser maior que a capacidade."
        unchecked = "this.capacidadeCarga = capacidadeCarga; this.pesoCarga = pesoCarga;"
        checked = """if (pesoCarga > capacidadeCarga) {
throw new IllegalArgumentException("peso acima da capacidade");
}
this.capacidadeCarga = capacidadeCarga;
this.pesoCarga = pesoCarga;"""

        self.assertTrue(_semantic_issues(requirements, unchecked))
        self.assertEqual((), _semantic_issues(requirements, checked))

    def test_diagnostic_guidance_explains_int_to_Double_conversion(self) -> None:
        diagnostic = "error: incompatible types: int cannot be converted to Double"

        guidance = _diagnostic_guidance(diagnostic)

        self.assertIn("(double)", guidance)
        self.assertIn("Double", guidance)


if __name__ == "__main__":
    unittest.main()
