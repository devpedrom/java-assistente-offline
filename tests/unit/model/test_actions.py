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

    def test_reject_non_object_arguments(self) -> None:
        with self.assertRaises(ActionValidationError):
            parse_action('{"tool":"read_file","args":["Veiculo.java"]}')


if __name__ == "__main__":
    unittest.main()

