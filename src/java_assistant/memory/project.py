"""Portable project memory; Java sources always remain the source of truth."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from .files import CanonicalFiles
from .models import RequirementSnapshot, SessionState, VerificationSnapshot
from .store import MemoryEvent, ProjectStore, pdf_sha256, project_identifier, text_sha256


@dataclass(frozen=True)
class SourceReconciliation:
    changed: tuple[str, ...]
    added: tuple[str, ...]
    removed: tuple[str, ...]
    unchanged: tuple[str, ...]


class ProjectMemory:
    @classmethod
    def open(cls, project_root: Path, legacy_state_dir: Path):
        memory = cls()
        memory.root = project_root.resolve(strict=True)
        memory.legacy = legacy_state_dir
        memory.files = CanonicalFiles.open(memory.root)
        memory.manifest = memory.files.load_manifest()
        memory.requirements = memory.files.load_requirements()
        memory.state = memory.files.load_state()
        memory.verifications = memory.files.load_verifications()
        memory.events = memory.files.recover()
        if any(not isinstance(event.get("kind"), str) or not isinstance(event.get("content"), str)
               or not isinstance(event.get("metadata", {}), dict) for event in memory.events):
            raise ValueError("Evento canônico inválido; fontes Java preservados.")
        memory.warnings = []
        memory._closed = False
        database = memory.files.path("memoria.db")
        for name in ("memoria.db", "memoria.db-wal", "memoria.db-shm"):
            raw = memory.root / ".assistente" / name
            if raw.is_symlink():
                raise ValueError("Cache de memória não pode usar links.")
        try:
            memory.cache = ProjectStore.open("projeto", memory.manifest.project_id, database.parent, database=database)
        except sqlite3.DatabaseError:
            for name in ("memoria.db", "memoria.db-wal", "memoria.db-shm"):
                path = memory.files.path(name)
                if path.exists():
                    destination = memory.files.path(f"recuperacao/{name}.{uuid4().hex}.corrompido")
                    destination.parent.mkdir(exist_ok=True)
                    path.rename(destination)
            memory.cache = ProjectStore.open("projeto", memory.manifest.project_id, database.parent, database=database)
            memory.warnings.append("Cache SQLite reconstruído a partir do diário.")
        memory.cache.rebuild(MemoryEvent(event["kind"], event["content"], event.get("created_at", ""), "projeto")
                             for event in memory.events)
        memory.reconcile_sources()
        snapshot = memory.verifications
        if (snapshot.compiled or snapshot.locally_tested) and not memory._verification_identity_matches():
            memory.invalidate("Requisitos ou critérios diferem das verificações; evidências invalidadas.")
        return memory

    def record_event(self, kind, content, metadata=None):
        if not isinstance(kind, str) or not kind.strip() or not isinstance(content, str) or not content.strip():
            raise ValueError("Evento de memória inválido.")
        event = {"id": uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
                 "kind": kind, "content": content, "metadata": metadata or {}}
        self.files.append_event(event)
        self.events.append(event)
        self.cache.remember(kind, content)

    def remember(self, kind, content):
        self.record_event(kind, content)
        if kind == "change":
            self.reconcile_sources()
        self.state = replace(self.state, last_operation=f"{kind}: {content[:1000]}")
        self.checkpoint()

    def import_legacy(self, pdf_hash):
        key = pdf_hash or "sem-pdf"
        if any(event["kind"] == "migration" and event.get("metadata", {}).get("pdf_hash") == key for event in self.events):
            return 0
        database = self.legacy / "memoria.sqlite3"
        count = 0
        if database.is_file():
            connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                rows = connection.execute("SELECT kind, content FROM events WHERE project_id=? AND pdf_hash=? ORDER BY id",
                                          (project_identifier(self.root), key)).fetchall()
                for kind, content in rows:
                    self.record_event(kind, content, {"legacy": True, "pdf_hash": key})
                    count += 1
            finally:
                connection.close()
        self.record_event("migration", "Importação legada concluída.", {"pdf_hash": key, "count": count})
        return count

    def _inventory(self):
        hashes = {}
        for path in sorted(self.root.rglob("*.java")):
            relative = path.relative_to(self.root)
            if ".assistente" in relative.parts:
                continue
            safe = self.files.workspace._resolve(relative)
            hashes[relative.as_posix()] = pdf_sha256(safe)
        return hashes

    def reconcile_sources(self):
        current = self._inventory()
        previous = self.state.source_hashes
        changed = tuple(sorted(name for name in current.keys() & previous.keys() if current[name] != previous[name]))
        added = tuple(sorted(current.keys() - previous.keys()))
        removed = tuple(sorted(previous.keys() - current.keys()))
        unchanged = tuple(sorted(name for name in current.keys() & previous.keys() if current[name] == previous[name]))
        if changed or added or removed:
            self.record_event("sources", "Inventário Java atualizado; verificações afetadas invalidadas.",
                              {"changed": changed, "added": added, "removed": removed})
            valid = {name: digest for name, digest in self.verifications.source_hashes.items() if current.get(name) == digest}
            self.verifications = replace(self.verifications, source_hashes=valid, compiled=False, structural=False,
                                         locally_tested=(), diagnostics="Fontes alterados; revalidar.")
            self.files.save_verifications(self.verifications)
            self.state = replace(self.state, source_hashes=current, phase="revalidar", next_action="Recompile e valide os fontes atuais.")
            self.checkpoint()
        return SourceReconciliation(changed, added, removed, unchanged)

    def select_requirements(self, contract, text, source, identity, pdf_path=None, criteria=""):
        if self.requirements and self.requirements.identity != identity:
            self.files._write(f"recuperacao/requisitos-v{self.requirements.version}-{self.requirements.identity}.json",
                              json.dumps(self.requirements.to_dict(), ensure_ascii=False))
        version = self.requirements.version + 1 if self.requirements and self.requirements.identity != identity else (self.requirements.version if self.requirements else 1)
        self.requirements = RequirementSnapshot(contract, text, source, identity, version)
        self.files.save_requirements(self.requirements)
        self.manifest = replace(self.manifest, pdf_path=pdf_path, pdf_hash=identity, criteria_hash=text_sha256(criteria))
        self.files.save_manifest(self.manifest)
        self.verifications = VerificationSnapshot(requirement_hash=identity, criteria_hash=text_sha256(criteria))
        self.files.save_verifications(self.verifications)
        self.record_event("requirements", f"Enunciado registrado, versão {version}.", {"identity": identity})
        self.state = replace(self.state, phase="implementar", next_action="Confira /contrato e peça a implementação.")
        self.checkpoint()

    def record_verification(self, compiled, *, structural=False, locally_tested=(), unproven=(), diagnostics="", sources=None):
        self.reconcile_sources()
        inventory = self._inventory()
        scope = inventory if sources is None else {
            name: inventory[name] for path in sources
            for name in [self.files.workspace._resolve(path).relative_to(self.root).as_posix()]
        }
        self.verifications = VerificationSnapshot(scope, compiled, structural, tuple(locally_tested),
            tuple(unproven), diagnostics[:8000], self.manifest.pdf_hash, self.manifest.criteria_hash)
        self.files.save_verifications(self.verifications)
        self.record_event("verification", diagnostics[:2000] or ("Compilação aprovada." if compiled else "Verificação falhou."))
        self.state = replace(self.state, phase="revisar" if compiled else "corrigir",
            next_action="Revise as evidências e regras não comprovadas." if compiled else "Corrija a última falha e recompile.")
        self.checkpoint()

    def invalidate(self, reason):
        self.verifications = VerificationSnapshot(diagnostics=reason)
        self.files.save_verifications(self.verifications)
        self.record_event("invalidation", reason)
        self.state = replace(self.state, phase="revalidar", next_action="Confira o enunciado e valide novamente.")
        self.checkpoint()

    def update_criteria(self, criteria):
        digest = text_sha256(criteria)
        changed = self.manifest.criteria_hash is not None and self.manifest.criteria_hash != digest
        if self.manifest.criteria_hash != digest:
            self.manifest = replace(self.manifest, criteria_hash=digest)
            self.files.save_manifest(self.manifest)
        if changed:
            self.invalidate("Critérios gerais mudaram; verificações invalidadas.")
        return changed

    def load_verifications(self):
        return self.verifications

    def has_valid_compilation(self):
        return self.verifications.compiled and self.verifications.source_hashes == self._inventory() and self._verification_identity_matches()

    def _verification_identity_matches(self):
        identity = self.requirements.identity if self.requirements else None
        return (self.verifications.requirement_hash == self.manifest.pdf_hash == identity
                and self.verifications.criteria_hash == self.manifest.criteria_hash)

    def summary(self, max_chars=4000):
        return self.cache.summary(max_chars=max_chars)

    def build_context(self, criteria, target_class=None, max_chars=8000):
        parts = [criteria]
        if target_class and self.requirements:
            parts.append("Alvo: " + target_class)
            parts.extend("Superclasse: " + relation.parent for relation in self.requirements.contract.relationships
                         if relation.child == target_class and relation.kind == "inheritance")
        parts.extend(("Última verificação: " + self.verifications.diagnostics,
                      "Próxima ação: " + self.next_action(), self.summary(max_chars=max_chars)))
        return "\n".join(parts)[:max_chars]

    def next_action(self):
        return self.state.next_action

    def status_summary(self):
        return (f"Fase: {self.state.phase}\nPDF/enunciado: {self.manifest.pdf_path or ('texto colado' if self.requirements else 'nenhum')}"
                f"\nArquivos: {len(self.state.source_hashes)}\nÚltima verificação: {self.verifications.diagnostics or 'nenhuma'}"
                f"\nPróxima ação: {self.next_action()}")

    def checkpoint(self):
        self.files.write_context(self.build_context("", max_chars=4000))
        self.files.write_next_action(self.next_action())
        self.files.save_state(self.state)

    def close(self):
        if not self._closed:
            try:
                self.checkpoint()
            finally:
                self.cache.close()
                self._closed = True
