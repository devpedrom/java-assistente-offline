"""Atomic canonical files, confined to a project's hidden memory directory."""

import json
import os
from pathlib import Path
from uuid import uuid4

from java_assistant.workspace.files import Workspace
from .models import ProjectManifest, RequirementSnapshot, SessionState, VerificationSnapshot


class CanonicalFiles:
    def __init__(self, root: Path):
        self.workspace = Workspace(root)

    def path(self, name: str) -> Path:
        relative = Path(".assistente") / name
        path = self.workspace._resolve(relative)
        memory = self.workspace.root / ".assistente"
        if memory.is_symlink():
            raise ValueError("A pasta .assistente não pode ser um link.")
        try:
            path.relative_to(memory)
        except ValueError as error:
            raise ValueError("Caminho fora da memória do projeto.") from error
        return path

    @classmethod
    def open(cls, project_root):
        files = cls(project_root)
        manifest = files.path("projeto.json")
        manifest.parent.mkdir(exist_ok=True)
        if not manifest.exists():
            files.save_manifest(ProjectManifest(uuid4().hex))
        files.load_manifest()
        return files

    def _write(self, name, text):
        self.path(name)
        self.workspace.write(Path(".assistente") / name, text)

    def _save(self, name, value):
        text = json.dumps(value.to_dict(), ensure_ascii=False, indent=2) + "\n"
        type(value).from_dict(json.loads(text))
        path = self.path(name)
        if path.is_file():
            # A backup is updated only from a schema-valid document.
            previous = path.read_text(encoding="utf-8")
            type(value).from_dict(json.loads(previous))
            self._write("recuperacao/" + name, previous)
        self._write(name, text)

    def _load(self, name, model, optional=False):
        path = self.path(name)
        if not path.exists() and optional:
            return None
        try:
            return model.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            backup = self.path("recuperacao/" + name)
            if backup.is_file():
                text = backup.read_text(encoding="utf-8")
                recovered = model.from_dict(json.loads(text))
                self._write(name, text)
                return recovered
            raise ValueError(f"Memória inválida em {name}; fontes Java preservados.") from error

    def load_manifest(self): return self._load("projeto.json", ProjectManifest)
    def save_manifest(self, value): self._save("projeto.json", value)
    def load_requirements(self): return self._load("requisitos.json", RequirementSnapshot, True)
    def save_requirements(self, value): self._save("requisitos.json", value)
    def load_state(self): return self._load("estado.json", SessionState, True) or SessionState()
    def save_state(self, value): self._save("estado.json", value)
    def load_verifications(self): return self._load("verificacoes.json", VerificationSnapshot, True) or VerificationSnapshot()
    def save_verifications(self, value): self._save("verificacoes.json", value)
    def write_context(self, text): self._write("contexto.md", text)
    def write_next_action(self, text): self._write("proxima_acao.md", text)

    def append_event(self, event):
        text = json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"
        path = self.path("decisoes.jsonl")
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

    def recover(self):
        path = self.path("decisoes.jsonl")
        if not path.exists():
            return []
        raw = path.read_bytes()
        lines = raw.splitlines(keepends=True)
        events = []
        for index, line in enumerate(lines):
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("Evento inválido.")
                events.append(event)
            except (ValueError, UnicodeError) as error:
                if index == len(lines) - 1 and not line.endswith(b"\n"):
                    self._write("recuperacao/diario-interrompido.jsonl", raw.decode("utf-8", errors="replace"))
                    self._write("decisoes.jsonl", b"".join(lines[:index]).decode("utf-8"))
                    break
                raise ValueError("Corrupção no meio do diário; fontes preservados.") from error
        else:
            if raw and not raw.endswith(b"\n"):
                self._write("decisoes.jsonl", raw.decode("utf-8") + "\n")
        return events
