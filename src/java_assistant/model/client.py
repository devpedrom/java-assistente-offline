from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ModelProtocolError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ModelReply:
    content: str


class ModelClient:
    def __init__(self, transport: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._transport = transport

    def complete(self, messages: list[Message]) -> ModelReply:
        payload = {
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ]
        }
        response = self._transport(payload)
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ModelProtocolError("Resposta incompleta do modelo local.") from error
        if not isinstance(content, str):
            raise ModelProtocolError("O conteudo retornado pelo modelo nao e texto.")
        return ModelReply(content=content)

