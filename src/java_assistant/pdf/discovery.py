"""Discovery used by the interactive ``/pdf`` command."""

from pathlib import Path


def discover_pdfs(root: Path) -> list[Path]:
    resolved = root.resolve(strict=True)
    if not resolved.is_dir():
        raise NotADirectoryError(resolved)
    return sorted(
        (
            item
            for item in resolved.iterdir()
            if item.is_file() and not item.is_symlink() and item.suffix.casefold() == ".pdf"
        ),
        key=lambda item: (item.name.casefold(), item.name),
    )
