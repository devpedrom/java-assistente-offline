import json
import unittest

from java_assistant.model.client import LocalHttpTransport, Message, ModelClient, ModelProtocolError


class ModelClientTests(unittest.TestCase):
    def test_http_transport_uses_only_loopback_chat_endpoint(self) -> None:
        captured = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"choices":[{"message":{"content":"ok"}}]}'

        def opener(request, timeout):
            captured.append((request, timeout))
            return Response()

        result = LocalHttpTransport(8081, opener=opener)({"messages": []})

        request, timeout = captured[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8081/v1/chat/completions")
        self.assertEqual(json.loads(request.data), {"messages": [], "temperature": 0.1})
        self.assertEqual(timeout, 120)
        self.assertEqual(result["choices"][0]["message"]["content"], "ok")

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

