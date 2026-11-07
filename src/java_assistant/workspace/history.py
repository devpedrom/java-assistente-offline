"""In-session change history with conflict-safe undo."""

from __future__ import annotations

from dataclasses import dataclass

from .files import Change, Workspace, PatchMismatchError, _digest, _UNCONDITIONAL


@dataclass(frozen=True)
class UndoResult:
    undone: bool
    reason: str


class History:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace
        self._changes: list[Change] = []

    def record(self, change: Change) -> None:
        self._changes.append(change)

    def write(self, relative: Path, content: str, *, expected=_UNCONDITIONAL) -> Change:
        change = self._workspace.write(relative, content, expected=expected)
        self.record(change)
        return change

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
            current = self._workspace.read(change.relative_path)
            if _digest(current) != change.after_hash:
                return UndoResult(False, "O arquivo mudou durante o desfazer.")
            try:
                self._workspace.write(change.relative_path, change.before_content, expected=current)
            except PatchMismatchError:
                return UndoResult(False, "O arquivo mudou durante o desfazer.")
        else:
            removed = self._workspace.remove_if_hash(
                change.relative_path, change.after_hash
            )
            if not removed:
                return UndoResult(False, "O arquivo mudou durante o desfazer.")

        self._changes.pop()
        return UndoResult(True, "Última alteração do assistente desfeita.")
