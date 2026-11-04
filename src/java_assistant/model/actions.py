from dataclasses import dataclass
import json
import re
from typing import Any


ALLOWED_TOOLS = frozenset({
    "read_file",
    "write_file",
    "apply_patch",
    "compile_java",
    "run_java",
    "select_pdf",
    "memory",
    "respond",
})


class ActionValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Action:
    tool: str
    args: dict[str, Any]


def parse_action(text: str) -> Action:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3 and lines[0].casefold() in {"```", "```json"} and lines[-1].strip() == "```":
            candidate = "\n".join(lines[1:-1]).strip()

    write_match = re.fullmatch(
        r'<write_file path="([^"\r\n]+)">\r?\n?(.*?)</write_file>',
        candidate,
        flags=re.DOTALL,
    )
    if write_match:
        return Action(
            tool="write_file",
            args={"path": write_match.group(1), "content": write_match.group(2)},
        )
    if re.fullmatch(r"<compile_java\s*/>", candidate):
        return Action(tool="compile_java", args={})
    run_match = re.fullmatch(
        r'<run_java main_class="([A-Za-z_$][A-Za-z0-9_$.]*)"\s*/>', candidate
    )
    if run_match:
        return Action(tool="run_java", args={"main_class": run_match.group(1)})
    respond_match = re.fullmatch(r"<respond>(.*?)</respond>", candidate, flags=re.DOTALL)
    if respond_match:
        return Action(tool="respond", args={"text": respond_match.group(1).strip()})

    try:
        value = json.loads(candidate)
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

