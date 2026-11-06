import importlib.util
from pathlib import Path
import unittest
from java_assistant.model.client import Message


class PortableTests(unittest.TestCase):
    def test_repairs_alternate_per_unit_and_preserve_sibling_choice(self):
        path = Path(__file__).resolve().parents[2]/'packaging/linux/portable/portable.py'
        spec = importlib.util.spec_from_file_location('portable', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        model = module.AlternatingModel(12345, 200, ['qwen', 'phi'], announce=lambda _: None)
        calls = []
        def transport(payload):
            calls.append(payload['model'])
            return {'choices': [{'message': {'content': 'source'}}]}
        model.transport = transport
        for unit, repair in [('Conta', False), ('Conta', True), ('Saldo', False), ('Conta', True)]:
            text = f'Escreva SOMENTE {unit}.java'
            if repair:
                text += '\nERRO DA VERIFICAÇÃO ANTERIOR: falha'
            model.complete([Message('user', text)])
        self.assertEqual(['qwen', 'phi', 'qwen', 'qwen'], calls)
