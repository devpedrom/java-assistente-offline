from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from java_assistant.core.spec import (
    Member,
    Requirement,
    Relationship,
    Specification,
    Unit,
    find_unit,
    members_of,
)
from java_assistant.pdf.extract import PdfEvidence
from java_assistant.uml.extract import UmlExtractor


def sample() -> Specification:
    return Specification(
        units=(
            Unit(
                name="Conta",
                kind="class",
                members=(
                    Member("saldo", "field", "double", "private"),
                    Member("Conta", "constructor", "Conta", "public"),
                    Member("depositar", "method", "void", "public", (("valor", "double"),)),
                ),
                confidence=0.98,
            ),
        ),
        relationships=(
            Relationship("Base", "Conta", "inheritance", 0.98),
        ),
        requirements=(
            Requirement("O saldo aumenta em 10%.", "pdf-text", 0.98, "Conta"),
        ),
        warnings=("aviso",),
    )


class SpecificationTests(unittest.TestCase):
    def test_round_trip_is_stable_and_returns_fresh_structures(self) -> None:
        spec = sample()

        first = spec.to_dict()
        first["units"][0]["name"] = "Alterado"
        first["units"][0]["members"][0]["name"] = "outro"

        self.assertEqual("Conta", spec.units[0].name)
        self.assertEqual("saldo", spec.units[0].members[0].name)
        self.assertEqual(spec, Specification.from_dict(spec.to_dict()))

    def test_rejects_invalid_kind_visibility_name_and_confidence(self) -> None:
        with self.assertRaises(ValueError):
            Unit("Conta", "struct", ())
        with self.assertRaises(ValueError):
            Member("saldo", "field", "double", "internal")
        with self.assertRaises(ValueError):
            Member("", "field", "double", "private")
        with self.assertRaises(ValueError):
            Relationship("Base", "Conta", "inheritance", 1.5)
        with self.assertRaises(ValueError):
            Requirement("   ", "pdf-text", 0.98)

    def test_from_dict_rejects_items_and_parameters_with_wrong_shape(self) -> None:
        with self.assertRaises(ValueError):
            Specification.from_dict({"units": ["Conta"]})
        with self.assertRaises(ValueError):
            Specification.from_dict(
                {
                    "units": [
                        {
                            "name": "Conta",
                            "kind": "class",
                            "members": [
                                {
                                    "name": "depositar",
                                    "kind": "method",
                                    "type_name": "void",
                                    "visibility": "public",
                                    "parameters": [["valor", "double", "extra"]],
                                }
                            ],
                        }
                    ]
                }
            )

    def test_find_unit_and_members_of_filter_by_kind(self) -> None:
        spec = sample()
        unit = find_unit(spec, "Conta")

        self.assertIsNotNone(unit)
        assert unit is not None
        self.assertEqual(("saldo",), tuple(item.name for item in members_of(unit, "field")))
        self.assertEqual(
            ("Conta",), tuple(item.name for item in members_of(unit, "constructor"))
        )
        self.assertIsNone(find_unit(spec, "Inexistente"))


class UmlExtractionTests(unittest.TestCase):
    def test_extracts_interface_and_implements(self) -> None:
        evidence = PdfEvidence(
            "interface Pagavel\n"
            "+ pagar(valor: double): boolean\n"
            "class Boleto implements Pagavel\n"
            "+ pagar(valor: double): boolean\n",
            "text",
            (),
        )

        spec = UmlExtractor().extract(evidence)

        payable = find_unit(spec, "Pagavel")
        self.assertIsNotNone(payable)
        assert payable is not None
        self.assertEqual("interface", payable.kind)
        self.assertIn(
            ("Pagavel", "Boleto", "implements"),
            [(item.parent, item.child, item.kind) for item in spec.relationships],
        )

    def test_keeps_existing_class_herda_de_and_arrow_formats(self) -> None:
        evidence = PdfEvidence(
            "CLASSE: Veiculo\n"
            "- placa: String\n"
            "CLASSE: Carro\n"
            "Herda de: Veiculo\n"
            "+ portas: int\n"
            "Veiculo <|-- Caminhao\n",
            "text",
            (),
        )

        spec = UmlExtractor().extract(evidence)

        self.assertEqual(("Veiculo", "Carro"), tuple(u.name for u in spec.units))
        relations = {(item.parent, item.child, item.kind) for item in spec.relationships}
        self.assertIn(("Veiculo", "Carro", "inheritance"), relations)
        self.assertIn(("Veiculo", "Caminhao", "inheritance"), relations)

    def test_extracts_prose_class_headings_constructors_and_methods(self) -> None:
        evidence = PdfEvidence(
            "Classe Conta:\n"
            "  Construtor: Conta(String nome, Double saldo, int numero)\n"
            "  saldo: Double\n"
            "  calculaSaldo(): Retorna saldo com desconto de 10% para impostos.\n"
            "Classe Especial:\n"
            "  Construtor: Especial(int numero, String categoria, String nome, "
            "Double saldo)\n"
            "  categoria: “A” ou “B”.\n"
            "  calculaSaldo():\n"
            "    A: acréscimo de 30%.\n"
            "    B: acréscimo de 10%.\n"
            "    Aplicar desconto de 10% de impostos.\n",
            "text",
            (),
        )

        spec = UmlExtractor().extract(evidence)

        self.assertEqual(("Conta", "Especial"), tuple(u.name for u in spec.units))
        account = find_unit(spec, "Conta")
        assert account is not None
        constructor = members_of(account, "constructor")[0]
        self.assertEqual(
            ("nome", "saldo", "numero"),
            tuple(name for name, _ in constructor.parameters),
        )
        self.assertEqual(
            ("String", "Double", "int"),
            tuple(type_name for _, type_name in constructor.parameters),
        )
        salary = members_of(account, "method")[0]
        self.assertEqual("calculaSaldo", salary.name)
        self.assertEqual("Double", salary.type_name)
        special = find_unit(spec, "Especial")
        assert special is not None
        self.assertIn(
            "categoria", tuple(member.name for member in members_of(special, "field"))
        )
        self.assertEqual(
            {"Conta", "Especial"},
            {item.scope for item in spec.requirements},
        )

    def test_requirements_are_scoped_by_heading_and_preamble_is_general(self) -> None:
        evidence = PdfEvidence(
            "Regra geral: o valor nunca pode ser maior que o limite.\n"
            "class Conta\n"
            "+ depositar(valor: double): void\n"
            "O saldo aumenta em 10%.\n"
            "class Reserva\n"
            "A reserva e reduzida pela metade.\n",
            "text",
            (),
        )

        spec = UmlExtractor().extract(evidence)

        general = [item for item in spec.requirements if item.scope is None]
        account = [item for item in spec.requirements if item.scope == "Conta"]
        reserve = [item for item in spec.requirements if item.scope == "Reserva"]
        self.assertTrue(any("nunca pode ser maior" in item.text for item in general))
        self.assertTrue(any("aumenta em 10%" in item.text for item in account))
        self.assertTrue(any("reduzida pela metade" in item.text for item in reserve))

    def test_ocr_source_lowers_confidence_and_keeps_the_warning(self) -> None:
        evidence = PdfEvidence(
            "class Conta\n+ total(): Double\n",
            "ocr",
            ("Conteúdo obtido por OCR; confirme nomes e símbolos do UML.",),
        )

        spec = UmlExtractor().extract(evidence)

        self.assertEqual(0.8, spec.units[0].confidence)
        self.assertEqual(0.8, spec.requirements[0].confidence)
        self.assertIn("OCR", " ".join(spec.warnings))

    def test_empty_evidence_still_produces_a_warning(self) -> None:
        spec = UmlExtractor().extract(PdfEvidence("texto sem classes", "text", ()))

        self.assertEqual((), spec.units)
        self.assertTrue(any("Nenhuma classe" in item for item in spec.warnings))


if __name__ == "__main__":
    unittest.main()
