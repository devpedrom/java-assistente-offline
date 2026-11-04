from collections.abc import Callable
from dataclasses import dataclass
import json
from typing import Any
from urllib.request import Request, urlopen


class ModelProtocolError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ModelReply:
    content: str
    truncated: bool = False


class LocalHttpTransport:
    """OpenAI-compatible transport hard-wired to the local llama-server."""

    def __init__(self, port: int, *, opener: Callable[..., Any] = urlopen) -> None:
        if port < 1 or port > 65535:
            raise ValueError("Porta local inválida.")
        self._url = f"http://127.0.0.1:{port}/v1/chat/completions"
        self._opener = opener

    def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = dict(payload)
        body.setdefault("temperature", 0.1)
        body.setdefault("max_tokens", 384)
        request = Request(
            self._url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener(request, timeout=600) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ModelProtocolError(f"Falha na comunicação com o modelo local: {error}") from error
        if not isinstance(decoded, dict):
            raise ModelProtocolError("O modelo local retornou uma resposta inválida.")
        return decoded


class ModelClient:
    def __init__(self, transport: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._transport = transport

    def complete(
        self, messages: list[Message], *, max_tokens: int | None = None
    ) -> ModelReply:
        payload = {
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ]
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        response = self._transport(payload)
        try:
            choice = response["choices"][0]
            content = choice["message"]["content"]
            truncated = choice.get("finish_reason") == "length"
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise ModelProtocolError("Resposta incompleta do modelo local.") from error
        if not isinstance(content, str):
            raise ModelProtocolError("O conteudo retornado pelo modelo nao e texto.")
        return ModelReply(content=content, truncated=truncated)

