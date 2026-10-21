import unittest

from java_assistant.model.client import Message, ModelClient, ModelProtocolError


class ModelClientTests(unittest.TestCase):
    def test_complete_returns_assistant_content(self) -> None:
        captured: list[dict] = []

        def transport(payload: dict) -> dict:
            captured.append(payload)
            return {"choices": [{"message": {"role": "assistant", "content": "Resposta"}}]}

        client = ModelClient(transport)
        reply = client.complete([Message("user", "O que e heranca?")])

        self.assertEqual("Resposta", reply.content)
        self.assertEqual(
            [{"role": "user", "content": "O que e heranca?"}],
            captured[0]["messages"],
        )

    def test_complete_rejects_incomplete_response(self) -> None:
        client = ModelClient(lambda _payload: {"choices": []})

        with self.assertRaises(ModelProtocolError):
            client.complete([Message("user", "Oi")])


if __name__ == "__main__":
    unittest.main()

