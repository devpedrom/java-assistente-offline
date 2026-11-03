from pathlib import Path
import unittest


FORBIDDEN = ("Frota", "Hatch", "Pickup", "calculaVolume", "autonomia")


class NoFixtureLeakTests(unittest.TestCase):
    def test_product_sources_do_not_mention_the_fixture(self) -> None:
        root = Path(__file__).parents[2] / "src"
        offenders = [
            f"{path.relative_to(root)}: {name}"
            for path in root.rglob("*.py")
            for name in FORBIDDEN
            if name.casefold() in path.read_text(encoding="utf-8").casefold()
        ]

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
