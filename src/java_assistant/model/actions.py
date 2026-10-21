from dataclasses import dataclass
import json
from typing import Any


ALLOWED_TOOLS = frozenset({
    "read_file",
    "write_file",
    "apply_patch",
    "compile_java",
    "run_java",
    "select_pdf",
    "memory",
})


class ActionValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Action:
    tool: str
    args: dict[str, Any]


def parse_action(text: str) -> Action:
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, TypeError) as error:
        raise ActionValidationError("A acao precisa ser um objeto JSON valido.") from error

    if not isinstance(value, dict):
        raise ActionValidationError("A acao precisa ser um objeto JSON.")
    tool = value.get("tool")
    args = value.get("args")
    if tool not in ALLOWED_TOOLS:
        raise ActionValidationError("Ferramenta nao permitida.")
    if not isinstance(args, dict):
        raise ActionValidationError("Os argumentos precisam formar um objeto.")
    return Action(tool=tool, args=args)

