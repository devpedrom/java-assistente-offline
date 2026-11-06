"""JDK-backed source positions and validation for body-only corrections."""

import base64
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import tempfile

from .toolchain import JavaToolchain
from .validator import ContractValidator
from java_assistant.workspace.files import PatchMismatchError


@dataclass(frozen=True)
class MethodBody:
    name: str
    parameter_types: tuple[str, ...]
    start: int
    end: int
    signature: str


def locate_methods(toolchain: JavaToolchain, relative: Path, owner: str) -> tuple[MethodBody, ...]:
    if ".." in Path(relative).parts:
        raise ValueError("A fonte deve permanecer dentro do projeto.")
    path = toolchain._source(relative)
    source = path.read_bytes().decode("utf-8")
    with tempfile.TemporaryDirectory(prefix="java-assistente-ast-") as temp:
        helper = Path(__file__).with_name("MethodBodies.java")
        compiled = subprocess.run(
            [toolchain.javac, "-proc:none", "-encoding", "UTF-8", "-d", temp, str(helper)],
            cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
        if compiled.returncode:
            raise ValueError("Não foi possível preparar o analisador Java: " + compiled.stderr[-2000:])
        result = subprocess.run(
            [toolchain.java, "-cp", temp, "MethodBodies", str(path), owner],
            cwd=temp, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        if result.returncode:
            raise ValueError("Não foi possível analisar os métodos: " + result.stderr[-2000:])
    encoded = source.encode("utf-16-le")
    def position(value):
        offset = int(value)
        if not 0 <= offset <= len(encoded)//2:
            raise ValueError("Posição Java inválida.")
        return len(encoded[:offset*2].decode("utf-16-le"))
    def decoded(value):
        return base64.b64decode(value, validate=True).decode("utf-8")
    methods = []
    for line in result.stdout.splitlines():
        name, parameters, start, end, signature = line.split("\t")
        methods.append(MethodBody(decoded(name), tuple(decoded(parameters).splitlines()),
                                  position(start), position(end), decoded(signature)))
    return tuple(methods)


def extract_body(text: str) -> str:
    body = text.strip()
    fenced = re.fullmatch(r"```(?:java)?\s*\n(.*)\n```", body, re.S | re.I)
    if fenced:
        body = fenced.group(1).strip()
    if not body.startswith("{") or not body.endswith("}"):
        raise ValueError("Responda somente com o corpo Java entre chaves.")
    return body


def validate_method(workspace, toolchain, contract, relative, method, body, expected_source) -> str:
    def unchanged():
        if workspace.read(relative) != expected_source:
            raise PatchMismatchError("O arquivo mudou durante a correção; edição preservada.")

    unchanged()
    if workspace.root != toolchain.root:
        raise ValueError("A análise precisa usar a mesma raiz do projeto.")
    if method not in locate_methods(toolchain, relative, Path(relative).stem):
        raise ValueError("O método não corresponde ao fonte atual.")
    body = extract_body(body)
    candidate = expected_source[:method.start] + body + expected_source[method.end:]
    with tempfile.TemporaryDirectory(prefix="java-assistente-candidato-") as temp:
        staging = Path(temp)
        for source in sorted(workspace.root.rglob("*.java")):
            name = source.relative_to(workspace.root)
            content = workspace.read(name)
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((candidate if name == relative else content).encode("utf-8"))
        staged = JavaToolchain(staging, toolchain.javac, toolchain.java, toolchain.javap)
        try:
            found = locate_methods(staged, relative, Path(relative).stem)
            if not any(item.name == method.name and item.parameter_types == method.parameter_types
                       and item.signature == method.signature and item.start == method.start
                       and item.end == method.start + len(body) for item in found):
                raise ValueError("A resposta precisa alterar somente o corpo selecionado.")
            report = ContractValidator(staged).validate(contract, staging)
            if not report.valid:
                raise ValueError("Candidato recusado: " + "\n".join(report.issues))
        finally:
            staged.close()
    unchanged()
    return candidate
