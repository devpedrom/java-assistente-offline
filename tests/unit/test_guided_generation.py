import unittest

from java_assistant.adapters.java8 import Java8Adapter
from java_assistant.core.spec import Unit


class GuidedGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = Java8Adapter()
        self.unit = Unit("Veiculo", "class", ())

    def test_extracts_plain_or_fenced_single_class_source(self) -> None:
        plain = "public class Veiculo {}"
        fenced = "```java\npublic class Veiculo {}\n```"

        self.assertEqual(plain + "\n", self.adapter.parse_unit_source(plain, self.unit))
        self.assertEqual(
            plain + "\n", self.adapter.parse_unit_source(fenced, self.unit)
        )

    def test_extracts_first_write_block_even_if_model_added_more_actions(self) -> None:
        reply = (
            '<write_file path="Veiculo.java">\npublic class Veiculo {}\n</write_file>\n'
            "<compile_java />"
        )

        self.assertEqual(
            "public class Veiculo {}\n",
            self.adapter.parse_unit_source(reply, self.unit),
        )

    def test_rejects_wrong_or_multiple_public_classes(self) -> None:
        with self.assertRaises(ValueError):
            self.adapter.parse_unit_source("public class Carro {}", self.unit)
        with self.assertRaises(ValueError):
            self.adapter.parse_unit_source(
                "public class Veiculo {}\npublic class Carro {}", self.unit
            )

    def test_diagnostic_guidance_explains_int_to_Double_conversion(self) -> None:
        diagnostic = "error: incompatible types: int cannot be converted to Double"

        guidance = self.adapter.diagnostic_hint(diagnostic)

        self.assertIn("(double)", guidance)
        self.assertIn("Double", guidance)


if __name__ == "__main__":
    unittest.main()
