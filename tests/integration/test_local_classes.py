from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from java_assistant.core.spec import Member, Relationship, Specification, Unit, find_unit
from java_assistant.java.local_classes import LocalClassAdopter
from java_assistant.java.toolchain import JavaToolchain


VEICULO = """public class Veiculo {
  private int passageiros;
  private Double rendimento;
  public Veiculo() {}
  public Veiculo(int passageiros, Double rendimento) {
    this.passageiros = passageiros;
    this.rendimento = rendimento;
  }
  public Double autonomia() { return rendimento * 10; }
  public int getPassageiros() { return passageiros; }
  public void setPassageiros(int passageiros) { this.passageiros = passageiros; }
}
"""

CARRO = """public class Carro extends Veiculo {
  private boolean cambioAutomatico;
  public Carro() {}
  public Carro(int passageiros, Double rendimento, boolean cambioAutomatico) {
    super(passageiros, rendimento);
    this.cambioAutomatico = cambioAutomatico;
  }
  public boolean isCambioAutomatico() { return cambioAutomatico; }
}
"""

EXTRA = """public class Extra {
  public int valor() { return 1; }
}
"""

RUNNER = """public class Runner {
  public static void main(String[] args) {}
}
"""

TEXT = """Veiculo:
autonomia(): retorna o rendimento.
Carro:
autonomia() reduz em 10% quando o cambio e automatico.
Runner:
testa os metodos.
"""


def _compile(directory: Path, names: tuple[str, ...]) -> None:
    subprocess.run(
        ["javac", "-d", str(directory), *(str(directory / f"{name}.java") for name in names)],
        check=True,
        capture_output=True,
    )


@unittest.skipUnless(shutil.which("javac"), "javac nao esta no PATH")
class LocalClassAdopterTests(unittest.TestCase):
    def test_adopts_members_and_hierarchy_from_compiled_classes(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            reference = root / "Classes de teste"
            reference.mkdir()
            for name, source in (
                ("Veiculo", VEICULO),
                ("Carro", CARRO),
                ("Extra", EXTRA),
                ("Runner", RUNNER),
            ):
                (reference / f"{name}.java").write_text(source, encoding="utf-8")
            _compile(reference, ("Veiculo", "Carro", "Extra", "Runner"))

            base = Specification(
                units=(
                    Unit(
                        "Veiculo",
                        "class",
                        (
                            Member("passageiros", "field", "int", "protected"),
                            Member("inventado", "method", "void", "public"),
                        ),
                    ),
                ),
                relationships=(
                    Relationship(
                        "Veiculo",
                        "Carro",
                        "ambiguous",
                        0.5,
                        ("association", "aggregation", "composition"),
                    ),
                ),
                requirements=(),
            )
            spec, adopted, checkers = LocalClassAdopter(
                root, javap=JavaToolchain(root).javap
            ).adopt(base, TEXT, "text")

        self.assertEqual(set(adopted), {"Veiculo", "Carro"})
        self.assertEqual(("Runner",), checkers)
        self.assertNotIn("Extra", adopted)
        self.assertNotIn("Runner", adopted)
        veiculo = find_unit(spec, "Veiculo")
        carro = find_unit(spec, "Carro")
        assert veiculo is not None and carro is not None
        fields = {member.name: member for member in veiculo.members if member.kind == "field"}
        self.assertEqual(fields["passageiros"].visibility, "private")
        self.assertIn(
            "getPassageiros", {member.name for member in veiculo.members}
        )
        self.assertNotIn(
            "inventado", {member.name for member in veiculo.members}
        )
        constructor = next(
            member
            for member in carro.members
            if member.kind == "constructor" and member.parameters
        )
        self.assertEqual(
            [type_name for _, type_name in constructor.parameters],
            ["int", "Double", "boolean"],
        )
        self.assertIn(
            ("Veiculo", "Carro", "inheritance"),
            [
                (item.parent, item.child, item.kind)
                for item in spec.relationships
            ],
        )
        self.assertFalse(
            any(item.alternatives for item in spec.relationships),
            spec.relationships,
        )
        self.assertEqual(
            [requirement.scope for requirement in spec.requirements],
            ["Veiculo", "Carro"],
        )
        carro_scope = next(
            item.text for item in spec.requirements if item.scope == "Carro"
        )
        self.assertIn("10%", carro_scope)


if __name__ == "__main__":
    unittest.main()
