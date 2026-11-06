"""In-session change history with conflict-safe undo."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
import json
from pathlib import Path
import re

from .files import Change, Workspace, PatchMismatchError, _digest


@dataclass(frozen=True)
class UndoResult:
    undone: bool
    reason: str


class History:
    def __init__(self, workspace: Workspace, recovery=None) -> None:
        self._workspace = workspace
        self._recovery = recovery
        self._changes: list[Change] = []
        if recovery:
            path = recovery.path("recuperacao/alteracoes.json")
            if path.exists():
                try:
                    self._changes = self._decode(path.read_text(encoding="utf-8"))
                except (ValueError, OSError):
                    backup = recovery.path("recuperacao/alteracoes-anteriores.json")
                    recovered = backup.read_text(encoding="utf-8")
                    self._changes = self._decode(recovered)
                    recovery._write("recuperacao/alteracoes.json", recovered)
                while self._changes:
                    last = self._changes[-1]
                    if self._workspace.current_hash(last.relative_path) != last.before_hash:
                        break
                    self._changes.pop()

    def _decode(self, text):
        try:
            data = json.loads(text)
            if data["schema_version"] != 1 or not isinstance(data["changes"], list):
                raise ValueError("Histórico inválido.")
            changes = []
            for item in data["changes"]:
                path = Path(item["path"])
                resolved = self._workspace._resolve(path)
                if ".assistente" in resolved.relative_to(self._workspace.root).parts:
                    raise ValueError("Histórico não pode alterar memória canônica.")
                existed = item["existed_before"]
                before = item["before_content"]
                if type(existed) is not bool or (existed and not isinstance(before, str)) or (not existed and before is not None):
                    raise ValueError("Conteúdo anterior inválido.")
                digest = _digest(before) if before is not None else None
                if item["before_hash"] != digest or not re.fullmatch(r"[a-f0-9]{64}", item["after_hash"]):
                    raise ValueError("Hashes do histórico inválidos.")
                changes.append(Change(path, existed, before, digest, item["after_hash"]))
            return changes
        except (KeyError, TypeError) as error:
            raise ValueError("Histórico de recuperação inválido; fontes preservados.") from error

    def _persist(self, changes):
        if self._recovery:
            text = json.dumps({"schema_version": 1, "changes": [
                {"path": c.relative_path.as_posix(), "existed_before": c.existed_before,
                 "before_content": c.before_content, "before_hash": c.before_hash, "after_hash": c.after_hash}
                for c in changes
            ]}, ensure_ascii=False)
            self._decode(text)
            path = self._recovery.path("recuperacao/alteracoes.json")
            if path.exists():
                previous = path.read_text(encoding="utf-8")
                self._decode(previous)
                self._recovery._write("recuperacao/alteracoes-anteriores.json", previous)
            self._recovery._write("recuperacao/alteracoes.json", text)

    def write(self, relative: Path, content: str, *, expected: str | None = None) -> Change:
        path = self._workspace._resolve(relative).relative_to(self._workspace.root)
        before_hash = self._workspace.current_hash(path)
        before = self._workspace.read(path) if before_hash is not None else None
        if expected is not None and before != expected:
            raise PatchMismatchError("O arquivo mudou durante a correção; edição preservada.")
        intent = Change(path, before is not None, before, before_hash, _digest(content))
        self._persist([*self._changes, intent])
        if before is not None:
            change = self._workspace.apply_patch(path, before, content)
        else:
            change = self._workspace.write(path, content)
        self._changes.append(change)
        return change

    def record(self, change: Change) -> None:
        self._changes.append(change)
        self._persist(self._changes)

    def render_changes(self) -> str:
        if not self._changes:
            return "Nenhuma alteração do assistente nesta sessão."
        first: dict = {}
        last: dict = {}
        for change in self._changes:
            first.setdefault(change.relative_path, change)
            last[change.relative_path] = change
        parts = []
        for path, change in last.items():
            if self._workspace.current_hash(path) != change.after_hash:
                parts.append(f"{path}: arquivo alterado depois; diferença não atribuída ao assistente.")
                continue
            before = first[path].before_content or ""
            after = self._workspace.read(path)
            parts.append("".join(unified_diff(
                before.splitlines(keepends=True), after.splitlines(keepends=True),
                fromfile=str(path), tofile=str(path),
            )))
        return "\n".join(parts) or "Nenhuma diferença restante."

    def undo_last(self) -> UndoResult:
        if not self._changes:
            return UndoResult(False, "Nenhuma alteração do assistente para desfazer.")

        change = self._changes[-1]
        if self._workspace.current_hash(change.relative_path) != change.after_hash:
            return UndoResult(
                False,
                "O arquivo foi alterado depois; a edição posterior foi preservada.",
            )

        if change.existed_before:
            assert change.before_content is not None
            self._workspace.write(change.relative_path, change.before_content)
        else:
            removed = self._workspace.remove_if_hash(
                change.relative_path, change.after_hash
            )
            if not removed:
                return UndoResult(False, "O arquivo mudou durante o desfazer.")

        self._changes.pop()
        self._persist(self._changes)
        return UndoResult(True, "Última alteração do assistente desfeita.")
