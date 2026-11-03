# Memoria Portatil Entre Sessoes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o assistente retomar automaticamente um exercicio na mesma pasta, preservando requisitos, decisoes, hashes, verificacoes e proxima acao em `.assistente`, sem Graphify e sem trocar o modelo local.

**Architecture:** Arquivos JSON/JSONL atomicos dentro do projeto serao a fonte canonica; um SQLite local sera apenas indice reconstruivel. Uma fachada `ProjectMemory` reconciliara os arquivos Java atuais com o ultimo checkpoint, produzira um contexto curto e integrara checkpoints ao ciclo existente de `AssistantSession`.

**Tech Stack:** Python 3.10+, biblioteca padrao (`dataclasses`, `json`, `sqlite3`, `hashlib`, `os`, `uuid`, `pathlib`), `unittest`, Java 8 e ferramentas ja empacotadas.

**Spec:** `docs/superpowers/specs/2026-10-22-memoria-portatil-entre-sessoes-design.md`

## Global Constraints

- Linux Mint x86-64, CPU sem GPU dedicada e 4 a 6 GB de RAM.
- Operacao 100% offline, sem API, banco vetorial, Graphify ou processo adicional.
- Usar somente o modelo GGUF e o `llama.cpp` ja empacotados; nao criar adaptadores de modelo.
- Estado canonico em `<projeto>/.assistente`; `CRITERIOS_GERAIS.md` continua na configuracao global.
- SQLite e cache reconstruivel, nunca a unica copia de requisitos ou decisoes.
- Nenhuma inconsistencia de memoria pode apagar ou sobrescrever fontes Java.
- Persistir apenas fatos, decisoes, evidencias, erros e proximas acoes; nao armazenar raciocinio privado do modelo.
- Manter compatibilidade com Python 3.10 e codigo Java 8.
- Nao incluir alteracoes preexistentes e nao relacionadas nos commits das tarefas.
- Em arquivos que ja estavam modificados antes deste plano (`session.py`, testes de sessao, documentacao e aceitacao), registrar o diff inicial e usar staging parcial; nunca executar `git add` do arquivo inteiro sem provar que somente os novos hunks serao incluidos.

## Review Focus

- Processo interrompido entre escrita temporaria e substituicao: `test_interrupted_atomic_write_keeps_last_valid_state` na Task 2 deve provar recuperacao.
- Arquivo Java editado fora do assistente: `test_reconcile_invalidates_only_changed_source_evidence` na Task 4 deve preservar o fonte e invalidar somente sua evidencia.
- Pasta movida ou renomeada: `test_manifest_identity_survives_project_move` na Task 2 deve manter o UUID gravado.
- `memoria.db` corrompido ou ausente: `test_rebuilds_sqlite_cache_from_canonical_files` na Task 3 deve recuperar decisoes sem perda.
- PDF trocado mantendo o mesmo nome: `test_pdf_hash_change_versions_contract_and_invalidates_dependent_evidence` na Task 5 deve detectar pelo hash, nao pelo caminho.

---

## File Structure

- Create `src/java_assistant/memory/models.py`: dataclasses e validacao dos documentos canonicos.
- Create `src/java_assistant/memory/files.py`: leitura e substituicao atomica de JSON, JSONL e Markdown confinadas a `.assistente`.
- Create `src/java_assistant/memory/project.py`: fachada de identidade, checkpoint, reconciliacao, recuperacao e contexto.
- Modify `src/java_assistant/memory/store.py`: transformar o SQLite em cache por projeto, enumerar/importar eventos e permitir reconstrucao.
- Modify `src/java_assistant/memory/__init__.py`: exportar as novas interfaces publicas.
- Modify `src/java_assistant/uml/models.py`: serializacao e desserializacao deterministica de `JavaContract`.
- Modify `src/java_assistant/session.py`: restaurar estado, persistir marcos e implementar `/estado` e `/memoria` sobre a nova fachada.
- Modify `src/java_assistant/cli.py`: exibir a mensagem de retomada antes do primeiro prompt.
- Modify `docs/USO-RAPIDO.md`: explicar retomada e a pasta oculta.
- Modify `tests/acceptance/run-offline.sh`: provar retomada em dois processos no Linux.
- Modify `tests/acceptance/checklist.md`: registrar o novo gate manual/automatizado.
- Create `tests/unit/memory/test_models.py`.
- Create `tests/unit/memory/test_files.py`.
- Create `tests/unit/memory/test_project.py`.
- Modify `tests/unit/memory/test_store.py`.
- Modify `tests/integration/test_session_flow.py`.
- Modify `tests/unit/test_cli.py`.

### Task 1: Documentos canonicos e contrato Java serializavel

**Files:**
- Create: `src/java_assistant/memory/models.py`
- Modify: `src/java_assistant/uml/models.py`
- Modify: `src/java_assistant/memory/__init__.py`
- Create: `tests/unit/memory/test_models.py`

**Interfaces:**
- Consumes: `JavaContract`, `JavaClass`, `JavaMember`, `Relationship` existentes.
- Produces: `contract_to_dict(contract: JavaContract) -> dict[str, object]`, `contract_from_dict(data: dict[str, object]) -> JavaContract`, `ProjectManifest.from_dict/to_dict`, `RequirementSnapshot.from_dict/to_dict`, `SessionState.from_dict/to_dict` e `VerificationSnapshot.from_dict/to_dict`.

- [ ] **Step 1: Escrever testes que fixem round-trip, valores padrao e rejeicao de esquema invalido**

```python
def test_contract_round_trip_preserves_members_relationships_and_warnings():
    restored = contract_from_dict(contract_to_dict(CONTRACT))
    self.assertEqual(CONTRACT, restored)

def test_manifest_rejects_unknown_schema_version():
    with self.assertRaisesRegex(ValueError, "versão"):
        ProjectManifest.from_dict({"schema_version": 99, "project_id": "id"})
```

Cobrir tambem campos ausentes, tipos errados, `project_id` vazio e copia defensiva de mapas/listas.

- [ ] **Step 2: Executar os testes e confirmar a falha inicial**

Run: `python -m unittest tests.unit.memory.test_models -v`
Expected: FAIL por modulos/simbolos ainda inexistentes.

- [ ] **Step 3: Implementar serializacao do contrato em `uml/models.py`**

Adicionar exatamente:

```python
def contract_to_dict(contract: JavaContract) -> dict[str, object]: ...
def contract_from_dict(data: dict[str, object]) -> JavaContract: ...
```

Validar nomes, sequencias, parametros, visibilidade, confianca e alternativas sem instalar biblioteca de schema.

- [ ] **Step 4: Implementar dataclasses canonicas em `memory/models.py`**

Adicionar `SCHEMA_VERSION = 1` e dataclasses imutaveis `ProjectManifest`, `RequirementSnapshot`, `SessionState` e `VerificationSnapshot`. Cada classe tera `to_dict()` e `from_dict()`; timestamps serao strings ISO-8601 e hashes SHA-256 serao strings hexadecimais ou `None` onde permitido.

- [ ] **Step 5: Exportar as interfaces e executar testes**

Run: `python -m unittest tests.unit.memory.test_models -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/java_assistant/memory/models.py src/java_assistant/memory/__init__.py src/java_assistant/uml/models.py tests/unit/memory/test_models.py
git commit -m "feat: define canonical project memory documents"
```

### Task 2: Repositorio atomico dentro de `.assistente`

**Files:**
- Create: `src/java_assistant/memory/files.py`
- Create: `tests/unit/memory/test_files.py`

**Interfaces:**
- Consumes: dataclasses canonicas da Task 1 e uma raiz de projeto ja resolvida.
- Produces: `CanonicalFiles.open(project_root: Path) -> CanonicalFiles`, `load_manifest()`, `save_manifest()`, `load/save_requirements()`, `load/save_state()`, `load/save_verifications()`, `append_event(event: dict[str, object])`, `write_context(text: str)`, `write_next_action(text: str)` e `recover()`.

- [ ] **Step 1: Escrever testes de confinamento, atomicidade, diario e identidade movel**

```python
def test_interrupted_atomic_write_keeps_last_valid_state():
    files.save_state(VALID_STATE)
    with patch("java_assistant.memory.files.os.replace", side_effect=OSError("queda")):
        with self.assertRaises(OSError):
            files.save_state(NEW_STATE)
    self.assertEqual(VALID_STATE, files.load_state())

def test_manifest_identity_survives_project_move():
    project_id = files.load_manifest().project_id
    shutil.move(source, destination)
    self.assertEqual(project_id, CanonicalFiles.open(destination).load_manifest().project_id)
```

Cobrir JSON invalido, linha JSONL truncada no fim, symlink de `.assistente` para fora da raiz e ausencia de arquivos opcionais.

- [ ] **Step 2: Executar os testes e confirmar a falha inicial**

Run: `python -m unittest tests.unit.memory.test_files -v`
Expected: FAIL por `CanonicalFiles` inexistente.

- [ ] **Step 3: Implementar raiz protegida e escrita atomica**

`CanonicalFiles.open()` deve criar `.assistente` somente dentro da raiz real, rejeitar symlink que escape e usar arquivo temporario no mesmo diretorio, `flush`, `os.fsync` e `os.replace`. O manifesto inicial recebe `uuid.uuid4().hex`; reabertura nunca recalcula identidade pelo caminho.

- [ ] **Step 4: Implementar JSONL tolerante apenas a ultima linha interrompida**

`append_event()` escreve um objeto por linha e sincroniza antes de retornar. `recover()` pode ignorar/remover somente uma ultima linha incompleta; corrupcao no meio do diario deve ser reportada, nao ocultada.

- [ ] **Step 5: Executar os testes de memoria de arquivos**

Run: `python -m unittest tests.unit.memory.test_files -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/java_assistant/memory/files.py tests/unit/memory/test_files.py
git commit -m "feat: persist project state atomically"
```

### Task 3: SQLite reconstruivel e migracao da memoria legada

**Files:**
- Modify: `src/java_assistant/memory/store.py`
- Create: `src/java_assistant/memory/project.py`
- Modify: `tests/unit/memory/test_store.py`
- Create: `tests/unit/memory/test_project.py`

**Interfaces:**
- Consumes: `CanonicalFiles` e eventos JSONL das Tasks 1-2; banco legado em `AppConfig.state_dir` quando existir.
- Produces: `ProjectStore.open(database: Path, project_id: str)`, `events() -> tuple[MemoryEvent, ...]`, `rebuild(events: Iterable[MemoryEvent]) -> None`, `ProjectMemory.open(project_root: Path, legacy_state_dir: Path) -> ProjectMemory` e `import_legacy(pdf_hash: str | None) -> int`.

- [ ] **Step 1: Ajustar testes do store para banco explicitamente localizado no projeto**

Testar que `.assistente/memoria.db` usa WAL/FULL, filtra pelo UUID do manifesto e retorna eventos em ordem. Preservar um teste de leitura do formato legado atual para migracao.

- [ ] **Step 2: Escrever testes de reconstrucao e importacao unica**

```python
def test_rebuilds_sqlite_cache_from_canonical_files():
    memory.record_event("decision", "Usar herança")
    memory.close()
    (root / ".assistente" / "memoria.db").write_bytes(b"corrompido")
    reopened = ProjectMemory.open(root, legacy)
    self.assertIn("Usar herança", reopened.summary())

def test_legacy_events_are_imported_only_once():
    self.assertEqual(1, memory.import_legacy("pdf-hash"))
    self.assertEqual(0, memory.import_legacy("pdf-hash"))
```

- [ ] **Step 3: Executar testes e confirmar falhas**

Run: `python -m unittest tests.unit.memory.test_store tests.unit.memory.test_project -v`
Expected: FAIL nas novas assinaturas/reconstrucao.

- [ ] **Step 4: Refatorar `ProjectStore` sem perder leitura legada**

Introduzir `MemoryEvent` imutavel. Separar abertura do caminho do banco da identidade do projeto. Se a abertura retornar `sqlite3.DatabaseError`, renomear o cache corrompido para `recuperacao/memoria.db.corrompido` e reconstruir a partir do diario, sem tocar em fontes Java.

- [ ] **Step 5: Implementar a fachada inicial `ProjectMemory`**

`ProjectMemory.open()` abre `CanonicalFiles`, assegura manifesto, recupera o diario, abre/reconstroi o SQLite e marca a migracao legada no diario. `record_event(kind, content, metadata)` grava primeiro no JSONL e depois atualiza o cache.

- [ ] **Step 6: Executar testes e a regressao do modulo de memoria**

Run: `python -m unittest discover -s tests/unit/memory -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/java_assistant/memory/store.py src/java_assistant/memory/project.py tests/unit/memory/test_store.py tests/unit/memory/test_project.py
git commit -m "feat: rebuild project memory cache from journal"
```

### Task 4: Reconciliacao de fontes e contexto compacto

**Files:**
- Modify: `src/java_assistant/memory/project.py`
- Modify: `tests/unit/memory/test_project.py`

**Interfaces:**
- Consumes: estado, verificacoes, diario e arquivos `*.java` atuais.
- Produces: `SourceReconciliation(changed, added, removed, unchanged)`, `ProjectMemory.reconcile_sources()`, `record_verification(...)`, `build_context(criteria: str, target_class: str | None, max_chars: int = 8000) -> str`, `status_summary() -> str` e `next_action() -> str`.

- [ ] **Step 1: Escrever testes de hashes, invalidacao seletiva e limite de contexto**

```python
def test_reconcile_invalidates_only_changed_source_evidence():
    result = memory.reconcile_sources()
    self.assertEqual(("Hatch.java",), result.changed)
    self.assertNotIn("Hatch.java", memory.load_verifications().source_hashes)
    self.assertIn("Carro.java", memory.load_verifications().source_hashes)
    self.assertEqual(USER_EDIT, (root / "Hatch.java").read_text())

def test_context_is_bounded_and_prioritizes_target_parent_and_last_failure():
    context = memory.build_context(CRITERIA, "Hatch", max_chars=2000)
    self.assertLessEqual(len(context), 2000)
    self.assertIn("Hatch", context)
    self.assertIn("Carro", context)
    self.assertIn("última falha", context)
```

Cobrir fonte removido, arquivo novo, nenhum PDF e historico grande.

- [ ] **Step 2: Executar testes e confirmar falhas**

Run: `python -m unittest tests.unit.memory.test_project -v`
Expected: FAIL por metodos ainda inexistentes.

- [ ] **Step 3: Implementar hashing e reconciliacao sem escrever nos fontes**

Usar leitura binaria SHA-256. Invalidar verificacoes por arquivo/hash; nao invalidar requisitos ou decisoes. Atualizar inventario apenas depois de registrar o evento de alteracao externa.

- [ ] **Step 4: Implementar montagem deterministica do contexto**

Prioridade fixa: criterios, requisitos da classe alvo, contrato alvo/pais, fonte alvo/pais, ultima falha, decisoes vigentes e proxima acao. Truncar primeiro eventos antigos e fontes nao relacionadas; nunca cortar no meio do JSON do contrato usado internamente.

- [ ] **Step 5: Executar testes**

Run: `python -m unittest tests.unit.memory.test_project -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/java_assistant/memory/project.py tests/unit/memory/test_project.py
git commit -m "feat: reconcile sources and build resume context"
```

### Task 5: Integracao continua com `AssistantSession`

**Files:**
- Modify: `src/java_assistant/session.py:168-203`
- Modify: `src/java_assistant/session.py:405-574`
- Modify: `src/java_assistant/session.py:586-651`
- Modify: `src/java_assistant/session.py:660-835`
- Modify: `tests/integration/test_session_flow.py`

**Interfaces:**
- Consumes: `ProjectMemory` das Tasks 3-4, `JavaContract` serializavel e resultados atuais de toolchain/validator.
- Produces: `AssistantSession.resume_message: str`, checkpoints apos PDF, decisao, escrita, compilacao, validacao, execucao e saida; restauracao de `_contract`, `_pdf_text`, `_ambiguities` e evidencia valida.

- [ ] **Step 1: Escrever teste de duas sessoes sobre a mesma pasta**

```python
def test_second_session_restores_pdf_contract_and_next_action_without_pdf_command():
    first = make_session(root)
    select_fixture_pdf(first)
    first.close()
    second = make_session(root)
    self.assertIn("Projeto retomado", second.resume_message)
    self.assertIsNotNone(second._contract)
    self.assertNotIn("Use /pdf", second.handle("/estado").text)
```

Adicionar testes para checkpoint apos `workspace.write`, decisao de ambiguidade, compilacao falha/sucesso e `/sair` idempotente.

- [ ] **Step 2: Escrever o teste de troca de PDF pelo hash**

```python
def test_pdf_hash_change_versions_contract_and_invalidates_dependent_evidence():
    load_pdf(session, ORIGINAL_BYTES)
    replace_same_name_pdf(root, DIFFERENT_BYTES)
    reopened = make_session(root)
    self.assertIn("PDF mudou", reopened.resume_message)
    self.assertFalse(reopened.memory.has_valid_compilation())
```

- [ ] **Step 3: Executar os testes de integracao e confirmar falhas**

Run: `python -m unittest tests.integration.test_session_flow -v`
Expected: FAIL por ausencia de restauracao/checkpoints.

- [ ] **Step 4: Substituir o `ProjectStore` direto pela fachada `ProjectMemory`**

No construtor, abrir a memoria antes de montar a mensagem de retomada, reconciliar fontes e restaurar os documentos canonicos. Manter um adaptador pequeno `remember()` na fachada se isso reduzir alteracoes mecanicas, mas nenhum novo evento pode existir apenas no SQLite.

- [ ] **Step 5: Persistir cada marco validado**

Depois de escrita Java, registrar hashes e proxima acao. Depois de compilacao/validacao/execucao, persistir diagnostico, sucesso e hashes exatos. Salvar contrato e texto extraido ao selecionar PDF. Persistir decisao resolvida antes de solicitar nova geracao.

- [ ] **Step 6: Restaurar sem repetir trabalho aprovado**

Se PDF e fontes mantiverem hashes, restaurar contrato e evidencias. Se uma geracao foi interrompida, retomar pela primeira classe ausente ou pela ultima falha registrada. Nao chamar o modelo durante o construtor.

- [ ] **Step 7: Executar testes de integracao e regressao dirigida**

Run: `python -m unittest tests.integration.test_session_flow tests.unit.test_guided_generation -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -p src/java_assistant/session.py tests/integration/test_session_flow.py
git diff --cached --check
git commit -m "feat: resume assistant sessions from project memory"
```

### Task 6: Experiencia de retomada, `/estado` e encerramento

**Files:**
- Modify: `src/java_assistant/cli.py`
- Modify: `src/java_assistant/session.py:814-835`
- Modify: `tests/unit/test_cli.py`
- Modify: `tests/integration/test_session_flow.py`

**Interfaces:**
- Consumes: `AssistantSession.resume_message`, `ProjectMemory.status_summary()` e `close()` idempotente.
- Produces: uma mensagem curta antes do primeiro prompt, `/estado`, `/memoria` compacta e flush final no `/sair`, EOF, `Ctrl+C` e excecao de inicializacao.

- [ ] **Step 1: Escrever testes da interface**

```python
def test_cli_prints_resume_message_once_before_first_prompt():
    run_cli(config, input_fn, session=FakeSession(resume_message="Projeto retomado"))
    self.assertEqual(1, output.getvalue().count("Projeto retomado"))

def test_estado_reports_phase_pdf_files_last_check_and_next_action():
    text = session.handle("/estado").text
    for label in ("Fase", "PDF", "Arquivos", "Última verificação", "Próxima ação"):
        self.assertIn(label, text)
```

Cobrir projeto novo, memoria vazia, `/memoria` limitado e `close()` chamado duas vezes.

- [ ] **Step 2: Executar testes e confirmar falhas**

Run: `python -m unittest tests.unit.test_cli tests.integration.test_session_flow -v`
Expected: FAIL nos novos comportamentos.

- [ ] **Step 3: Implementar mensagem unica e comandos**

Adicionar `resume_message` ao protocolo `SessionLike`. `run_cli` imprime somente mensagens nao vazias. `/estado` usa dados estruturados; `/memoria` mostra resumo limitado e nunca despeja JSONL/SQLite.

- [ ] **Step 4: Tornar encerramento idempotente e persistente**

`AssistantSession.close()` deve gravar ultimo estado valido uma vez e fechar recursos. O `finally` do CLI continua sendo a garantia para `/sair`, EOF, interrupcao e falha posterior ao inicio da sessao.

- [ ] **Step 5: Executar testes**

Run: `python -m unittest tests.unit.test_cli tests.integration.test_session_flow -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/java_assistant/cli.py tests/unit/test_cli.py
git add -p src/java_assistant/session.py tests/integration/test_session_flow.py
git diff --cached --check
git commit -m "feat: expose automatic session resume status"
```

### Task 7: Empacotamento, documentacao e aceitacao Linux

**Files:**
- Modify: `docs/USO-RAPIDO.md`
- Modify: `tests/acceptance/run-offline.sh`
- Modify: `tests/acceptance/checklist.md`

**Interfaces:**
- Consumes: comando `java-assistente` empacotado e pasta `.assistente` criada pelas tarefas anteriores.
- Produces: gate de aceitacao que inicia dois processos separados sobre a mesma pasta e comprova retomada offline.

- [ ] **Step 1: Adicionar um cenario de aceitacao que falha antes da funcionalidade**

O script deve criar um projeto temporario, executar a primeira sessao com fixture PDF/estado deterministico, encerrar, executar uma segunda sessao e exigir `Projeto retomado` sem reenviar `/pdf`. Usar `timeout` e caminhos com espacos/acentos.

- [ ] **Step 2: Executar a suite Python completa**

Run: `python -m unittest discover -s tests -v`
Expected: PASS sem rede.

- [ ] **Step 3: Atualizar documentacao e checklist**

Documentar que `.assistente` acompanha o exercicio, pode ser preservada para retomar e nao deve ser entregue se a competicao aceitar somente fontes. Explicar `/estado`, `/memoria` e que mover a pasta preserva a identidade.

- [ ] **Step 4: Montar o bundle e executar verificacoes de empacotamento**

Run: `python -m unittest tests.packaging.test_installer -v`
Expected: PASS.

Run: `bash packaging/linux/build-bundle.sh`
Expected: exit 0 e artefato dentro do limite rigido de 2 GB.

- [ ] **Step 5: Executar a aceitacao em Linux/WSL**

Run: `bash tests/acceptance/run-offline.sh`
Expected: PASS incluindo instalacao, primeira sessao, encerramento, segunda sessao e retomada. Registrar separadamente que WSL nao substitui a medicao final no Linux Mint real de 4 a 6 GB.

- [ ] **Step 6: Verificar ausencia de integracoes proibidas e estado do Git**

Run: `rg -n -i "graphify|graphiti|neo4j|falkordb|openai|anthropic|gemini" src packaging`
Expected: nenhum novo backend de memoria/modelo; ocorrencias preexistentes devem ser explicadas.

Run: `git status --short`
Expected: somente alteracoes deliberadas desta implementacao, alem das alteracoes preexistentes identificadas antes do inicio.

- [ ] **Step 7: Commit**

```bash
git add -p docs/USO-RAPIDO.md tests/acceptance/run-offline.sh tests/acceptance/checklist.md
git diff --cached --check
git commit -m "test: verify persistent offline session resume"
```

### Task 8: Verificacao final integrada

**Files:**
- Modify: nenhum arquivo, salvo correcao exigida por falha comprovada.

**Interfaces:**
- Consumes: todos os entregaveis das Tasks 1-7.
- Produces: evidencia final de regressao, retomada, seguranca de caminhos, bundle e limites conhecidos.

- [ ] **Step 1: Executar toda a suite em ambiente Python limpo do projeto**

Run: `python -m unittest discover -s tests -v`
Expected: todos os testes PASS.

- [ ] **Step 2: Executar verificacao de diff**

Run: `git diff --check`
Expected: nenhuma saida.

- [ ] **Step 3: Revisar os requisitos da especificacao contra evidencias**

Confirmar explicitamente os dez criterios da secao 12 da especificacao. Marcar como nao comprovados o tempo/RAM no Linux Mint real e qualquer avaliacao dos jurados que nao tenha sido executada.

- [ ] **Step 4: Revisar preservacao das alteracoes preexistentes**

Comparar o status inicial registrado antes da implementacao com o status final. Nenhum arquivo alheio deve ser revertido, sobrescrito ou incluido acidentalmente em commits.

- [ ] **Step 5: Commit de correcoes finais, se necessario**

```bash
git add <somente-arquivos-corrigidos>
git commit -m "fix: complete persistent memory verification"
```

Se nenhuma correcao for necessaria, nao criar commit vazio.
