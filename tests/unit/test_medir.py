import unittest

from tests.qualidade import medir


class FidelityMeterTests(unittest.TestCase):
    def test_text_fixture_contract_matches_expected(self) -> None:
        result = medir.run("E1")

        self.assertTrue(result.contract_ok)
        self.assertTrue(result.untouched)

    def test_contract_comparison_sees_type_and_visibility(self) -> None:
        expected, scope = medir._load_expected("E1")
        self.assertEqual(medir._shape(expected, scope), medir._shape(expected, scope))

        changed = medir.JavaContract(
            (medir.JavaClass("Conta", (medir.JavaMember("saldo", "int", "private"),), ()),),
            (),
        )
        self.assertNotEqual(medir._shape(expected, scope), medir._shape(changed, scope))


if __name__ == "__main__":
    unittest.main()
