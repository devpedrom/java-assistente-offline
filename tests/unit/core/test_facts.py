import unittest

from java_assistant.adapters.java8 import JavaMatchers
from java_assistant.core.facts import (
    Rule,
    extract_rules,
    issues,
    prompt_section,
    requirements_section,
)
from java_assistant.core.spec import Member, Requirement, Relationship, Specification, Unit


def spec_with(
    units: tuple[Unit, ...],
    requirements: tuple[Requirement, ...] = (),
    relationships: tuple[Relationship, ...] = (),
) -> Specification:
    return Specification(units=units, relationships=relationships, requirements=requirements)


def unit(name: str, *methods: str) -> Unit:
    return Unit(name, "class", tuple(Member(m, "method", "double", "public") for m in methods))


def requirement(text: str, scope: str | None = None) -> Requirement:
    return Requirement(text, "pdf-text", 0.98, scope)


def factors(spec: Specification) -> list[float]:
    return [rule.value for rule in extract_rules(spec) if rule.kind == "factor"]


class ExtractionTests(unittest.TestCase):
    def test_percentage_half_and_double_are_generic(self) -> None:
        spec = spec_with(
            (unit("Reserva"),),
            (
                requirement("O total aumenta em 25%."),
                requirement("O total reduz em 10%."),
                requirement("O total dobra."),
                requirement("O total e reduzido pela metade."),
                requirement("O total aumenta em 12,5%."),
            ),
        )

        self.assertEqual([1.25, 0.9, 2.0, 0.5, 1.125], factors(spec))

    def test_percentage_accepts_noun_forms_and_thousands(self) -> None:
        spec = spec_with(
            (unit("Item"),),
            (
                requirement("O total tem um aumento de 25%."),
                requirement("A reserva sofre reducao de 10%."),
                requirement("O total aumenta em 1.000%."),
            ),
        )

        self.assertEqual([1.25, 0.9, 11.0], factors(spec))

    def test_acrescimo_and_desconto_become_scoped_factors(self) -> None:
        spec = spec_with(
            (unit("Conta"), unit("Especial")),
            (
                requirement(
                    "Retorna saldo com desconto de 10% para impostos.", "Conta"
                ),
                requirement(
                    "A: acréscimo de 30%. B: acréscimo de 10%. "
                    "Aplicar desconto de 10% de impostos.",
                    "Especial",
                ),
            ),
        )

        rules = [
            (rule.unit, rule.value) for rule in extract_rules(spec) if rule.kind == "factor"
        ]

        self.assertEqual(
            [
                ("Conta", 0.9),
                ("Especial", 1.3),
                ("Especial", 1.1),
                ("Especial", 0.9),
            ],
            rules,
        )
        matchers = JavaMatchers()
        special = spec.units[1]
        self.assertEqual(
            (),
            issues(
                extract_rules(spec),
                special,
                "class Especial { Double calculaSaldo() { return 10.0 * 1.3 * 1.1 * 0.9; } }",
                matchers,
            ),
        )
        self.assertTrue(
            issues(
                extract_rules(spec),
                special,
                "class Especial { Double calculaSaldo() { return 10.0 * 1.3; } }",
                matchers,
            )
        )

    def test_prose_class_block_keeps_factor_inside_its_method(self) -> None:
        auxiliar = Unit(
            "Auxiliar",
            "class",
            (
                Member("setor", "field", "String", "private"),
                Member("calculaSalario", "method", "Double", "public"),
            ),
        )
        text = (
            "Construtor: Auxiliar(int registro, String setor, String nome, "
            "Double salario)\n"
            "  setor: “ACERVO” ou “LIMPEZA”.\n"
            "  calculaSalario():\n"
            "     ACERVO: acréscimo de 15%.\n"
            "     LIMPEZA: acréscimo de 5%.\n"
            "     Aplicar desconto de 10% de impostos.\n"
            "  organizarLivros(String): Recebe o gênero e retorna: "
            '"Livros de [gênero] organizados no [setor]."'
        )
        spec = spec_with((auxiliar,), (requirement(text, "Auxiliar"),))

        rules = [rule for rule in extract_rules(spec) if rule.kind == "factor"]

        self.assertEqual([1.15, 1.05, 0.9], [rule.value for rule in rules])
        self.assertTrue(all(rule.text.startswith("calculaSalario") for rule in rules))
        matchers = JavaMatchers()
        self.assertEqual(
            (),
            issues(
                rules,
                auxiliar,
                "class Auxiliar { Double calculaSalario() { "
                "return getSalario() * 1.15 * 1.05 * 0.9; } }",
                matchers,
            ),
        )
        self.assertTrue(
            issues(
                rules,
                auxiliar,
                "class Auxiliar { Double calculaSalario() { "
                "return getSalario() * 1.15; } }",
                matchers,
            )
        )

    def test_reduction_by_a_quarter_keeps_three_quarters(self) -> None:
        spec = spec_with((unit("Item"),), (requirement("A reserva e reduzida em um quarto."),))

        self.assertEqual([0.75], factors(spec))

    def test_upper_bound_requires_a_guard(self) -> None:
        spec = spec_with(
            (unit("Conta"),),
            (requirement("O saldo nunca pode ser maior que o limite.", "Conta"),),
        )
        rules = extract_rules(spec)
        matchers = JavaMatchers()

        self.assertEqual(
            [("upper_bound", "Conta")], [(rule.kind, rule.unit) for rule in rules]
        )
        self.assertTrue(issues(rules, spec.units[0], "this.saldo = saldo;", matchers))
        self.assertTrue(issues(rules, spec.units[0], "if (i > 0) { i = 1; }", matchers))
        self.assertEqual(
            (),
            issues(
                rules,
                spec.units[0],
                "if (saldo > limite) { throw new IllegalArgumentException(); }",
                matchers,
            ),
        )
        self.assertEqual(
            (),
            issues(
                rules,
                spec.units[0],
                "if (saldo > limite) {\n"
                '    throw new IllegalArgumentException("saldo acima do limite");\n'
                "}",
                matchers,
            ),
        )
        self.assertEqual(
            (),
            issues(rules, spec.units[0], "saldo = Math.min(saldo, limite);", matchers),
        )

    def test_division_rule_names_the_field_and_its_method(self) -> None:
        base = Unit(
            "Veiculo",
            "class",
            (Member("passageiros", "field", "int", "private"),),
        )
        child = Unit(
            "Moto",
            "class",
            (Member("autonomia", "method", "Double", "public"),),
        )
        spec = spec_with(
            (base, child),
            (requirement("autonomia(): divide pelo número de passageiros.", "Moto"),),
            (Relationship("Veiculo", "Moto", "inheritance", 1.0),),
        )
        rules = extract_rules(spec)
        matchers = JavaMatchers()

        self.assertEqual(
            [("divisor", "Moto", "passageiros")],
            [(rule.kind, rule.unit, rule.detail) for rule in rules if rule.kind == "divisor"],
        )
        self.assertTrue(
            issues(
                rules,
                child,
                "public Double autonomia() { "
                "return super.autonomia() / this.cilindrada; }",
                matchers,
            )
        )
        self.assertEqual(
            (),
            issues(
                rules,
                child,
                "public Double autonomia() { "
                "return super.autonomia() / getPassageiros(); }",
                matchers,
            ),
        )

    def test_factor_must_use_the_field_named_by_the_rule(self) -> None:
        caixa = Unit(
            "Caixa",
            "class",
            (
                Member("volume", "field", "double", "private"),
                Member("total", "method", "double", "public"),
            ),
        )
        spec = spec_with(
            (caixa,),
            (requirement("total: o volume dobra.", "Caixa"),),
        )
        rules = extract_rules(spec)
        matchers = JavaMatchers()

        self.assertTrue(
            issues(
                rules,
                caixa,
                "public double total(int x) { return x * 2.0; }",
                matchers,
            )
        )
        self.assertEqual(
            (),
            issues(
                rules,
                caixa,
                "public double total(int x) { return this.volume * 2.0; }",
                matchers,
            ),
        )

    def test_factor_named_by_the_rule_only_counts_inside_that_method(self) -> None:
        spec = spec_with(
            (unit("Caixa", "volume", "total"),),
            (requirement("volume: o volume dobra.", "Caixa"),),
        )
        rules = extract_rules(spec)
        matchers = JavaMatchers()

        self.assertTrue(
            issues(
                rules,
                spec.units[0],
                "public double volume() { return base; } "
                "public double total() { return base * 2.0; }",
                matchers,
            )
        )
        self.assertEqual(
            (),
            issues(
                rules,
                spec.units[0],
                "public double volume() { return base * 2.0; }",
                matchers,
            ),
        )

    def test_factor_named_by_rule_ignores_comments(self) -> None:
        caixa = Unit(
            "Caixa",
            "class",
            (
                Member("volume", "field", "double", "private"),
                Member("total", "method", "double", "public"),
            ),
        )
        spec = spec_with((caixa,), (requirement("total: o volume dobra.", "Caixa"),))

        found = issues(
            extract_rules(spec),
            caixa,
            "public double total() {\n"
            "    double taxa = 1.0;\n"
            "    return taxa * 2.0; // volume do bagageiro\n"
            "}",
            JavaMatchers(),
        )

        self.assertTrue(found)
        self.assertIn("volume", found[0])
        self.assertIn("2.0", found[0])

    def test_factor_on_parameter_is_reported_when_field_only_appears_in_condition(
        self,
    ) -> None:
        caixa = Unit(
            "Caixa",
            "class",
            (
                Member("volume", "field", "double", "private"),
                Member("total", "method", "double", "public", (("x", "int"),)),
            ),
        )
        spec = spec_with((caixa,), (requirement("total: o volume dobra.", "Caixa"),))

        found = issues(
            extract_rules(spec),
            caixa,
            "public double total(int x) { "
            "if (this.volume > 0) { return x * 2.0; } return 0.0; }",
            JavaMatchers(),
        )

        self.assertTrue(found)
        self.assertIn("volume", found[0])

    def test_integer_factor_on_parameter_is_reported_when_field_appears_in_condition(
        self,
    ) -> None:
        caixa = Unit(
            "Caixa",
            "class",
            (
                Member("volume", "field", "double", "private"),
                Member("total", "method", "double", "public", (("x", "int"),)),
            ),
        )
        spec = spec_with((caixa,), (requirement("total: o volume dobra.", "Caixa"),))

        found = issues(
            extract_rules(spec),
            caixa,
            "public double total(int x) { "
            "if (this.volume > 0) { return x * 2; } return 0.0; }",
            JavaMatchers(),
        )

        self.assertTrue(found)
        self.assertIn("volume", found[0])

    def test_factor_through_the_getter_is_accepted(self) -> None:
        caixa = Unit(
            "Caixa",
            "class",
            (
                Member("volume", "field", "double", "private"),
                Member("total", "method", "double", "public"),
            ),
        )
        spec = spec_with((caixa,), (requirement("total: o volume dobra.", "Caixa"),))

        self.assertEqual(
            (),
            issues(
                extract_rules(spec),
                caixa,
                "public double total() { return getVolume() * 2.0; }",
                JavaMatchers(),
            ),
        )

    def test_parameter_whose_name_is_a_suffix_of_a_local_is_not_the_factor_base(
        self,
    ) -> None:
        caixa = Unit(
            "Caixa",
            "class",
            (
                Member("volume", "field", "double", "private"),
                Member("total", "method", "double", "public", (("a", "int"),)),
            ),
        )
        spec = spec_with((caixa,), (requirement("total: o volume dobra.", "Caixa"),))

        self.assertEqual(
            (),
            issues(
                extract_rules(spec),
                caixa,
                "public double total(int a) { "
                "double taxa = this.volume; if (this.volume > 0) { return taxa * 2.0; } "
                "return 0.0; }",
                JavaMatchers(),
            ),
        )

    def test_two_factor_rules_in_one_method_need_both_literals(self) -> None:
        hatch = Unit(
            "Hatch",
            "class",
            (
                Member("bagageiro", "field", "int", "private"),
                Member(
                    "calculaVolume",
                    "method",
                    "Double",
                    "public",
                    (("passageiros", "int"),),
                ),
            ),
        )
        spec = spec_with(
            (hatch,),
            (
                requirement(
                    "calculaVolume: o volume do bagageiro aumenta em 100%.", "Hatch"
                ),
                requirement(
                    "calculaVolume: o volume do bagageiro aumenta em 50%.", "Hatch"
                ),
            ),
        )

        found = issues(
            extract_rules(spec),
            hatch,
            "public Double calculaVolume(int passageiros) { "
            "return this.bagageiro * 1.5; }",
            JavaMatchers(),
        )

        self.assertTrue(found)
        self.assertIn("2.0", " ".join(found))

    def test_factor_on_field_assigned_to_local_still_passes(self) -> None:
        caixa = Unit(
            "Caixa",
            "class",
            (
                Member("volume", "field", "double", "private"),
                Member("total", "method", "double", "public", (("x", "int"),)),
            ),
        )
        spec = spec_with((caixa,), (requirement("total: o volume dobra.", "Caixa"),))

        self.assertEqual(
            (),
            issues(
                extract_rules(spec),
                caixa,
                "public double total(int x) { "
                "double valor = this.volume; valor *= 2.0; return valor; }",
                JavaMatchers(),
            ),
        )

    def test_real_division_text_scopes_to_the_method(self) -> None:
        base = Unit(
            "Veiculo",
            "class",
            (Member("passageiros", "field", "int", "private"),),
        )
        child = Unit(
            "Moto",
            "class",
            (Member("autonomia", "method", "Double", "public"),),
        )
        spec = spec_with(
            (base, child),
            (
                requirement(
                    "autonomia(): altera o cálculo dividindo pelo número de passageiros.",
                    "Moto",
                ),
            ),
            (Relationship("Veiculo", "Moto", "inheritance", 1.0),),
        )

        found = issues(
            extract_rules(spec),
            child,
            "public Double outra() { return 500.0 / passageiros; }\n"
            "public Double autonomia() { return super.autonomia() / this.cilindrada; }",
            JavaMatchers(),
        )

        self.assertTrue(found)
        self.assertIn("no método autonomia", found[0])
        self.assertIn("passageiros", found[0])

    def test_prompt_section_uses_the_single_named_field(self) -> None:
        bonus = Unit(
            "Bonus",
            "class",
            (
                Member("salario", "field", "double", "public"),
                Member("calcular", "method", "double", "public"),
            ),
        )
        spec = spec_with((bonus,), (requirement("O salario aumenta em 50%.", "Bonus"),))

        text = prompt_section(extract_rules(spec), bonus)

        self.assertIn("salario * 1.5", text)

    def test_override_rule_forbids_arithmetic_over_super_without_scoped_requirement(
        self,
    ) -> None:
        spec = spec_with(
            (unit("Base", "total"), unit("Conta", "total")),
            relationships=(Relationship("Base", "Conta", "inheritance", 0.98),),
        )
        rules = extract_rules(spec)
        matchers = JavaMatchers()

        self.assertEqual(
            [Rule("super_call", "Conta", None, "total")], list(rules)
        )
        self.assertTrue(
            issues(rules, spec.units[1], "return super.total() * 0.5;", matchers)
        )
        self.assertEqual(
            (), issues(rules, spec.units[1], "return super.total();", matchers)
        )
        self.assertTrue(
            issues(
                rules,
                spec.units[1],
                "public double total() { return 7.0; }",
                matchers,
            )
        )

    def test_factor_already_applied_by_super_is_not_required_again(self) -> None:
        base = Unit(
            "Base",
            "class",
            (
                Member("valor", "field", "double", "private"),
                Member("total", "method", "double", "public"),
            ),
        )
        child = Unit(
            "Conta",
            "class",
            (Member("total", "method", "double", "public"),),
        )
        spec = spec_with(
            (base, child),
            (
                requirement("total(): aplica desconto de 10%.", "Base"),
                requirement(
                    "total(): acréscimo de 50% e desconto de 10%.", "Conta"
                ),
            ),
            relationships=(Relationship("Base", "Conta", "inheritance", 0.98),),
        )
        rules = extract_rules(spec)
        matchers = JavaMatchers()
        source = "public double total() { return super.total() * 1.5; }"

        self.assertEqual((), issues(rules, child, source, matchers, base))
        self.assertTrue(issues(rules, child, source, matchers))
        self.assertTrue(
            issues(rules, child, "return getValor() * 1.5;", matchers, base)
        )

    def test_global_requirement_about_method_allows_new_effect(self) -> None:
        spec = spec_with(
            (unit("Base", "total"), unit("Conta", "total")),
            (requirement("O total deve ser calculado novamente."),),
            relationships=(Relationship("Base", "Conta", "inheritance", 0.98),),
        )

        self.assertNotIn("super_call", [rule.kind for rule in extract_rules(spec)])

    def test_scoped_requirement_about_method_allows_new_effect(self) -> None:
        spec = spec_with(
            (unit("Base", "total"), unit("Conta", "total")),
            (requirement("O total desta classe soma 10%.", "Conta"),),
            relationships=(Relationship("Base", "Conta", "inheritance", 0.98),),
        )

        self.assertNotIn("super_call", [rule.kind for rule in extract_rules(spec)])

    def test_requirements_section_prioritizes_the_unit_scope(self) -> None:
        spec = spec_with(
            (unit("Conta"), unit("Reserva")),
            (
                requirement("Regra geral do enunciado."),
                requirement("Regra da Conta no fim do enunciado.", "Conta"),
                requirement("Regra de outra classe.", "Reserva"),
            ),
        )

        text = requirements_section(spec, spec.units[0])

        self.assertIn("[pdf-text | Conta] Regra da Conta no fim do enunciado.", text)
        self.assertIn("[pdf-text | geral] Regra geral do enunciado.", text)
        self.assertNotIn("outra classe", text)
        self.assertLess(
            text.index("Regra da Conta"),
            text.index("Regra geral"),
        )

    def test_requirements_section_names_owners_of_cited_methods(self) -> None:
        biblioteca = Unit(
            "Biblioteca",
            "class",
            (
                Member(
                    "executaTarefa",
                    "method",
                    "String",
                    "public",
                    (("funcionario", "Funcionario"), ("texto", "String")),
                ),
            ),
        )
        bibliotecario = Unit(
            "Bibliotecario",
            "class",
            (
                Member(
                    "processarEmprestimo",
                    "method",
                    "String",
                    "public",
                    (("texto", "String"),),
                ),
            ),
        )
        spec = spec_with(
            (biblioteca, bibliotecario),
            (
                requirement(
                    "executaTarefa retorna processarEmprestimo(String) para um "
                    "Bibliotecario.",
                    "Biblioteca",
                ),
            ),
        )

        text = requirements_section(spec, biblioteca)

        self.assertIn("processarEmprestimo(String) -> Bibliotecario", text)
        self.assertIn("Use exatamente estes nomes, sem renomear: processarEmprestimo.", text)
        self.assertIn("((Subclasse) objeto).metodo(texto)", text)

    def test_prompt_section_uses_only_requirement_text(self) -> None:
        spec = spec_with(
            (unit("Conta"), unit("Reserva")),
            (
                requirement("O total aumenta em 25%.", "Conta"),
                requirement("O saldo nunca pode ser maior que o limite.", "Conta"),
                requirement("O total reduz em 50%.", "Reserva"),
            ),
        )
        rules = extract_rules(spec)

        text = prompt_section(rules, spec.units[0])

        self.assertIn("O total aumenta em 25%", text)
        self.assertIn("base * 1.25", text)
        self.assertIn("O saldo nunca pode ser maior que o limite.", text)
        self.assertNotIn("50%", text)


if __name__ == "__main__":
    unittest.main()
