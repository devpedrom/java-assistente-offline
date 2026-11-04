"""Versioned SQLite store isolated by project and PDF identity."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3


_SCHEMA_VERSION = 1


def pdf_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def project_identifier(root: Path) -> str:
    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()


class ProjectStore:
    def __init__(
        self,
        connection: sqlite3.Connection,
        pdf_hash: str,
        project_id: str,
    ) -> None:
        self._connection = connection
        self.pdf_hash = pdf_hash
        self.project_id = project_id

    @classmethod
    def open(cls, pdf_hash: str, project_id: str, state_dir: Path) -> "ProjectStore":
        if not pdf_hash.strip() or not project_id.strip():
            raise ValueError("PDF e projeto precisam de identificadores não vazios.")
        state_dir.mkdir(parents=True, exist_ok=True)
        database = state_dir / "memoria.sqlite3"
        connection = sqlite3.connect(database, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        cls._migrate(connection)
        return cls(connection, pdf_hash, project_id)

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_info (version INTEGER NOT NULL)"
        )
        row = connection.execute("SELECT version FROM schema_info LIMIT 1").fetchone()
        if row is None:
            connection.execute("INSERT INTO schema_info(version) VALUES (0)")
            current = 0
        else:
            current = int(row[0])
        if current > _SCHEMA_VERSION:
            raise RuntimeError("A memória foi criada por uma versão mais nova do aplicativo.")
        if current < 1:
            connection.execute(
                """
                CREATE TABLE events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pdf_hash TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                "CREATE INDEX events_scope ON events(pdf_hash, project_id, id)"
            )
            connection.execute("UPDATE schema_info SET version = 1")
        connection.commit()

    def remember(self, kind: str, content: str) -> None:
        if not kind.strip() or not content.strip():
            raise ValueError("Tipo e conteúdo da memória não podem ser vazios.")
        with self._connection:
            self._connection.execute(
                "INSERT INTO events(pdf_hash, project_id, kind, content) VALUES (?, ?, ?, ?)",
                (self.pdf_hash, self.project_id, kind.strip(), content.strip()),
            )

    def summary(self, max_chars: int = 4000) -> str:
        if max_chars < 1:
            return ""
        rows = self._connection.execute(
            """
            SELECT kind, content
            FROM events
            WHERE pdf_hash = ? AND project_id = ?
            ORDER BY id DESC
            """,
            (self.pdf_hash, self.project_id),
        )
        selected: list[str] = []
        used = 0
        for kind, content in rows:
            line = f"[{kind}] {content}"
            separator = 1 if selected else 0
            remaining = max_chars - used - separator
            if remaining <= 0:
                break
            selected.append(line[:remaining])
            used += len(selected[-1]) + separator
        return "\n".join(selected)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "ProjectStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
