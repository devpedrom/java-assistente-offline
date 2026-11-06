from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import shutil

from java_assistant.java.toolchain import JavaToolchain

from tests.qualidade import medir


class QualityBehaviorTests(unittest.TestCase):
    def test_actual_validator_rejects_wrong_numbers_even_with_zero_exit_code(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixtures = Path(__file__).resolve().parents[1] / "fixtures/frota/classes-de-teste"
            for path in fixtures.glob("*.class"):
                shutil.copy2(path, root / path.name)
            (root / "Hatch.java").write_text(
                "public class Hatch extends Carro { public Hatch(int a,int b,Double c,boolean d,int e){super(a,b,c,d);} "
                "public Double autonomia(){return 0.0;} public Double calculaVolume(int n){return 0.0;} }",
                encoding="utf-8",
            )
            toolchain = JavaToolchain(root)
            try:
                compilation = toolchain.compile([Path("Hatch.java")])
                self.assertTrue(compilation.success, compilation.diagnostics)
                shutil.copy2(compilation.classes_dir / "Hatch.class", root / "Hatch.class")
                accepted, output = medir._validator(root)
                self.assertFalse(accepted, "A bateria imprime falhas numéricas mas termina com exit code zero.")
                self.assertIn("❌", output)
                shutil.copy2(fixtures / "Hatch.class", root / "Hatch.class")
                accepted, output = medir._validator(root)
                self.assertTrue(accepted, output)
                from tests.qualidade.validator import accepted as complete
                self.assertFalse(complete(output[:output.index("Carga inválida")]))
            finally:
                toolchain.close()

    def test_fixture_oracle_rejects_compiling_wrong_business_rule(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Conta.java").write_text(
                "public class Conta { private double saldo,limite; public Conta(double s,double l){saldo=s;limite=l;} "
                "public double getSaldo(){return saldo;} public boolean sacar(double v){return false;} }",
                encoding="utf-8",
            )
            (root / "ContaPoupanca.java").write_text(
                "public class ContaPoupanca extends Conta { private double taxa; "
                "public ContaPoupanca(double s,double l,double t){super(s,l);taxa=t;} public void render(){} }",
                encoding="utf-8",
            )
            result = medir.run("E1", root)
            self.assertTrue(result.compiled, result.reason)
            self.assertIs(result.behavior_ok, False, "Compilar não prova o aumento mensal de 2%.")
