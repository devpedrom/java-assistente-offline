#!/usr/bin/env python3
"""Monta o runtime sem extrair o arquivo nativo no disco."""

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path, PurePosixPath
import posixpath
import tarfile


REQUIRED_NATIVE = {
    "bin/java",
    "bin/javac",
    "bin/javap",
    "bin/pdftotext",
    "bin/pdftoppm",
    "bin/tesseract",
    "lib/libgomp.so.1",
    "share/tessdata/eng.traineddata",
    "share/tessdata/por.traineddata",
}


def _safe_member_name(name: str) -> str:
    path = PurePosixPath(name)
    parts = tuple(part for part in path.parts if part not in ("", "."))
    if path.is_absolute() or not parts or ".." in parts:
        raise ValueError(f"Caminho inseguro no runtime nativo: {name!r}")
    return "/".join(parts)


def _validate_symlink(member_name: str, target: str) -> None:
    if PurePosixPath(target).is_absolute():
        raise ValueError(f"Link absoluto proibido no runtime nativo: {target!r}")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(member_name), target))
    if resolved == ".." or resolved.startswith("../"):
        raise ValueError(f"Link escapa do runtime nativo: {member_name!r} -> {target!r}")


def _portable_metadata(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    if info.name in {
        "bin/java-assistente",
        "bin/desinstalar",
        "tools/llama/llama-server",
    }:
        info.mode = 0o755
    return info


def _source_filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    parts = PurePosixPath(info.name).parts
    if "__pycache__" in parts or info.name.endswith((".pyc", ".pyo")):
        return None
    return _portable_metadata(info)


def _append_native(destination: tarfile.TarFile, native_archive: Path) -> None:
    with tarfile.open(native_archive, "r:gz") as source:
        normalized = {
            _safe_member_name(member.name): member for member in source.getmembers()
            if member.name not in ("", ".", "./")
        }
        missing = sorted(REQUIRED_NATIVE.difference(normalized))
        if missing:
            raise ValueError(
                "Runtime nativo incompleto; ausentes: " + ", ".join(missing)
            )

        for name, member in normalized.items():
            cloned = copy.copy(member)
            cloned.name = f"tools/native/{name}"
            if cloned.issym():
                _validate_symlink(name, cloned.linkname)
            elif cloned.islnk():
                cloned.linkname = f"tools/native/{_safe_member_name(cloned.linkname)}"
            _portable_metadata(cloned)
            payload = source.extractfile(member) if member.isfile() else None
            destination.addfile(cloned, payload)


def assemble(project_root: Path, artifacts_dir: Path, output: Path) -> None:
    native_archive = artifacts_dir / "native.tar.gz"
    llama_dir = artifacts_dir / "llama"
    required_paths = (
        native_archive,
        llama_dir / "llama-server",
        project_root / "src" / "java_assistant",
        project_root / "instructions" / "CRITERIOS_GERAIS.md",
    )
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Artefatos ausentes: " + ", ".join(missing))

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with tarfile.open(temporary, "w:gz", compresslevel=6) as destination:
            _append_native(destination, native_archive)
            destination.add(
                llama_dir,
                arcname="tools/llama",
                recursive=True,
                filter=_source_filter,
            )
            destination.add(
                project_root / "src" / "java_assistant",
                arcname="app/java_assistant",
                recursive=True,
                filter=_source_filter,
            )
            destination.add(
                project_root / "instructions" / "CRITERIOS_GERAIS.md",
                arcname="share/CRITERIOS_GERAIS.md",
                filter=_source_filter,
            )
            destination.add(
                project_root / "packaging" / "linux" / "java-assistente",
                arcname="bin/java-assistente",
                filter=_source_filter,
            )
            destination.add(
                project_root / "packaging" / "linux" / "desinstalar.sh",
                arcname="bin/desinstalar",
                filter=_source_filter,
            )
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assemble(
        args.project_root.resolve(),
        args.artifacts_dir.resolve(),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
