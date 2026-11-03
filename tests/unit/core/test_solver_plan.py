import unittest

from java_assistant.core.solver import ContractStatus, Plan, classify, plan
from java_assistant.core.spec import Member, Requirement, Relationship, Specification, Unit


def member(name: str = "total", kind: str = "method") -> Member:
    return Member(name, kind, "double", "public")


def spec_with(
    units: tuple[Unit, ...],
    relationships: tuple[Relationship, ...] = (),
    requirements: tuple[Requirement, ...] = (),
) -> Specification:
    return Specification(
        units=units, relationships=relationships, requirements=requirements
    )


def plain(name: str, *members: Member, confidence: float = 1.0) -> Unit:
    return Unit(name, "class", members or (member(),), confidence=confidence)


class ClassifyTests(unittest.TestCase):
    def test_no_units_is_no_contract_and_ambiguous_relation_needs_confirmation(
        self,
    ) -> None:
        self.assertEqual(ContractStatus.NO_CONTRACT, classify(spec_with(())))
        self.assertEqual(
            ContractStatus.NEEDS_CONFIRMATION,
            classify(
                spec_with(
                    (plain("Base"), plain("Conta")),
                    (
                        Relationship(
                            "Base", "Conta", "inheritance", 0.98, ("Outra",)
                        ),
                    ),
                )
            ),
        )

    def test_ocr_confidence_080_needs_confirmation(self) -> None:
        self.assertEqual(
            ContractStatus.NEEDS_CONFIRMATION,
            classify(spec_with((plain("Conta", confidence=0.80),))),
        )
        self.assertEqual(
            ContractStatus.NEEDS_CONFIRMATION,
            classify(
                spec_with(
                    (plain("Conta"),),
                    requirements=(Requirement("O total dobra.", "ocr", 0.80),),
                )
            ),
        )

    def test_trusted_requires_all_units_confirmed_and_at_least_one_member(
        self,
    ) -> None:
        self.assertEqual(
            ContractStatus.TRUSTED,
            classify(
                spec_with(
                    (plain("Base"), plain("Conta")),
                    (Relationship("Base", "Conta", "inheritance", 0.98),),
                    (Requirement("O total dobra.", "pdf-text", 0.98),),
                )
            ),
        )
        self.assertEqual(
            ContractStatus.NEEDS_CONFIRMATION,
            classify(spec_with((Unit("Vazia", "class", ()),))),
        )
        self.assertEqual(
            ContractStatus.NEEDS_CONFIRMATION,
            classify(
                spec_with(
                    (plain("Conta"),),
                    (Relationship("Base", "Conta", "inheritance", 0.80),),
                )
            ),
        )


class PlanTests(unittest.TestCase):
    def test_plan_orders_parent_before_child_and_detects_cycle(self) -> None:
        ordered = plan(
            spec_with(
                (plain("Conta"), plain("Base"), plain("Animal")),
                (Relationship("Base", "Conta", "inheritance", 0.98),),
            )
        )
        cycle = plan(
            spec_with(
                (plain("A"), plain("B")),
                (
                    Relationship("A", "B", "inheritance", 0.98),
                    Relationship("B", "A", "inheritance", 0.98),
                ),
            )
        )

        self.assertEqual(("Animal", "Base", "Conta"), ordered.order)
        self.assertEqual((), ordered.issues)
        self.assertEqual(Plan(("A", "B"), None, cycle.issues), cycle)
        self.assertTrue(any("Ciclo" in issue for issue in cycle.issues))

    def test_plan_names_the_entry_point_and_flags_duplicates(self) -> None:
        static_main = Member("main", "method", "void", "public", modifiers=("static",))
        result = plan(
            spec_with(
                (
                    plain("Conta"),
                    plain("App", static_main),
                )
            )
        )
        duplicated = plan(spec_with((plain("Conta"), plain("Conta"))))
        ambiguous = plan(
            spec_with(
                (
                    plain("App", static_main),
                    plain("Zapp", static_main),
                )
            )
        )

        self.assertEqual("App", result.entry)
        self.assertIsNone(plan(spec_with((plain("Conta"),))).entry)
        self.assertIsNone(
            plan(spec_with((plain("App", Member("main", "method", "void", "public")),))).entry
        )
        self.assertTrue(any("duplicad" in issue for issue in duplicated.issues))
        self.assertEqual(("Conta",), duplicated.order)
        self.assertEqual("App", ambiguous.entry)
        self.assertTrue(any("Entrada ambígua" in issue for issue in ambiguous.issues))

    def test_relationship_to_unknown_unit_requires_confirmation(self) -> None:
        self.assertEqual(
            ContractStatus.NEEDS_CONFIRMATION,
            classify(
                spec_with(
                    (plain("Conta"),),
                    (Relationship("Bass", "Conta", "inheritance", 0.98),),
                )
            ),
        )

    def test_field_and_association_dependencies_order_type_before_owner(self) -> None:
        owner = Unit(
            "Owner",
            "class",
            (
                Member("item", "field", "Dependencia", "private"),
                Member("total", "method", "double", "public"),
            ),
        )
        field_ordered = plan(spec_with((owner, plain("Dependencia"), plain("Animal"))))
        association_ordered = plan(
            spec_with(
                (plain("Owner"), plain("Tipo")),
                (Relationship("Tipo", "Owner", "composition", 0.98),),
            )
        )

        self.assertEqual(("Animal", "Dependencia", "Owner"), field_ordered.order)
        self.assertEqual(("Tipo", "Owner"), association_ordered.order)
        self.assertEqual((), association_ordered.issues)

    def test_mutual_field_dependency_is_not_a_cycle(self) -> None:
        spec = spec_with(
            (
                Unit("A", "class", (Member("b", "field", "B", "private"),)),
                Unit("B", "class", (Member("a", "field", "A", "private"),)),
            )
        )

        result = plan(spec)

        self.assertEqual(("A", "B"), result.order)
        self.assertEqual((), result.issues)


if __name__ == "__main__":
    unittest.main()
