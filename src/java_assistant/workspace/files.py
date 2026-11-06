"""Safe file operations confined to one immutable project root."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile


class WorkspacePathError(ValueError):
    """Raised when a requested path can escape the project root."""


class PatchMismatchError(ValueError):
    """Raised when a patch does not match the current file exactly."""


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Change:
    relative_path: Path
    existed_before: bool
    before_content: str | None
    before_hash: str | None
    after_hash: str


class Workspace:
    """Reads and changes files without allowing access outside ``root``."""

    def __init__(self, root: Path) -> None:
        resolved = root.resolve(strict=True)
        if not resolved.is_dir():
            raise WorkspacePathError("A raiz do projeto precisa ser uma pasta.")
        self._root = resolved

    @property
    def root(self) -> Path:
        return self._root

    def _resolve(self, relative: Path) -> Path:
        candidate_input = Path(relative)
        if candidate_input.is_absolute():
            raise WorkspacePathError("Caminhos absolutos não são permitidos.")
        if not candidate_input.parts or any(part == ".." for part in candidate_input.parts):
            raise WorkspacePathError("O caminho precisa permanecer dentro do projeto.")

        candidate = (self._root / candidate_input).resolve(strict=False)
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise WorkspacePathError("O caminho sai da pasta do projeto.") from exc
        return candidate

    def _relative(self, path: Path) -> Path:
        return path.relative_to(self._root)

    def read(self, relative: Path) -> str:
        path = self._resolve(relative)
        if not path.is_file():
            raise FileNotFoundError(path)
        return path.read_bytes().decode("utf-8")

    def current_hash(self, relative: Path) -> str | None:
        path = self._resolve(relative)
        if not path.exists():
            return None
        if not path.is_file():
            raise WorkspacePathError("O destino não é um arquivo regular.")
        return _digest(path.read_bytes().decode("utf-8"))

    def write(self, relative: Path, content: str) -> Change:
        if not isinstance(content, str):
            raise TypeError("O conteúdo precisa ser texto.")
        path = self._resolve(relative)
        existed_before = path.exists()
        if existed_before and not path.is_file():
            raise WorkspacePathError("O destino não é um arquivo regular.")
        before_content = path.read_bytes().decode("utf-8") if existed_before else None

        path.parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = path.parent.resolve(strict=True)
        try:
            resolved_parent.relative_to(self._root)
        except ValueError as exc:
            raise WorkspacePathError("A pasta de destino sai do projeto.") from exc

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=resolved_parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

        return Change(
            relative_path=self._relative(path),
            existed_before=existed_before,
            before_content=before_content,
            before_hash=_digest(before_content) if before_content is not None else None,
            after_hash=_digest(content),
        )

    def apply_patch(self, relative: Path, expected: str, replacement: str) -> Change:
        current = self.read(relative)
        if current != expected:
            raise PatchMismatchError(
                "O arquivo mudou ou o trecho esperado não corresponde exatamente."
            )
        return self.write(relative, replacement)

    def remove_if_hash(self, relative: Path, expected_hash: str) -> bool:
        path = self._resolve(relative)
        if self.current_hash(relative) != expected_hash:
            return False
        path.unlink()
        return True
