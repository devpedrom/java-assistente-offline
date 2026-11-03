import unittest

from java_assistant.model.actions import ActionValidationError, parse_action


class ActionTests(unittest.TestCase):
    def test_parse_allowed_action(self) -> None:
        action = parse_action('{"tool":"read_file","args":{"path":"Veiculo.java"}}')

        self.assertEqual("read_file", action.tool)
        self.assertEqual({"path": "Veiculo.java"}, action.args)

    def test_reject_unknown_tool(self) -> None:
        with self.assertRaises(ActionValidationError):
            parse_action('{"tool":"shell","args":{"command":"rm -rf /"}}')

    def test_reject_malformed_json(self) -> None:
        with self.assertRaises(ActionValidationError):
            parse_action("use read_file now")

    def test_accepts_single_json_markdown_fence(self) -> None:
        action = parse_action(
            '```json\n{"tool":"read_file","args":{"path":"Veiculo.java"}}\n```'
        )

        self.assertEqual("read_file", action.tool)
        self.assertEqual("Veiculo.java", action.args["path"])

    def test_accepts_compact_write_file_block(self) -> None:
        action = parse_action(
            '<write_file path="Veiculo.java">\npublic class Veiculo {}\n</write_file>'
        )

        self.assertEqual("write_file", action.tool)
        self.assertEqual("Veiculo.java", action.args["path"])
        self.assertEqual("public class Veiculo {}\n", action.args["content"])

    def test_accepts_compact_compile_run_and_respond_blocks(self) -> None:
        compile_action = parse_action("<compile_java />")
        run_action = parse_action('<run_java main_class="Frota" />')
        respond_action = parse_action("<respond>Pronto.</respond>")

        self.assertEqual("compile_java", compile_action.tool)
        self.assertEqual({"main_class": "Frota"}, run_action.args)
        self.assertEqual({"text": "Pronto."}, respond_action.args)

    def test_reject_non_object_arguments(self) -> None:
        with self.assertRaises(ActionValidationError):
            parse_action('{"tool":"read_file","args":["Veiculo.java"]}')


if __name__ == "__main__":
    unittest.main()

