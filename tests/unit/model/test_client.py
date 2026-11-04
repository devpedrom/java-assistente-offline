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
        self.assertEqual(
            json.loads(request.data),
            {
                "messages": [],
                "temperature": 0.1,
                "max_tokens": 384,
            },
        )
        self.assertEqual(timeout, 600)
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

    def test_transport_accepts_per_call_max_tokens(self) -> None:
        captured: list[dict] = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read(self):
                return b'{"choices":[{"message":{"content":"ok"}}]}'

        def opener(request, timeout):
            captured.append(json.loads(request.data))
            return Response()

        LocalHttpTransport(1234, opener=opener)({"messages": [], "max_tokens": 1024})

        self.assertEqual(captured[0]["max_tokens"], 1024)

    def test_length_finish_reason_marks_reply_truncated(self) -> None:
        client = ModelClient(
            lambda _payload: {
                "choices": [
                    {"message": {"content": "class Conta {"}, "finish_reason": "length"}
                ]
            }
        )

        reply = client.complete([Message("user", "x")])

        self.assertTrue(reply.truncated)
        self.assertEqual("class Conta {", reply.content)


if __name__ == "__main__":
    unittest.main()

