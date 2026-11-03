# Núcleo genérico, perfil e adaptador Java 8 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status consolidado (2026-10-25):** T1–T13 executadas nesta worktree, sem commit, seguidas das correções P0/P1/P2 de intake textual, requisito longo e honestidade de execução. Os passos comprovados estão marcados abaixo; os únicos itens abertos são os gates externos de Linux Mint real e USB 2.0/hardware da competição. Checkpoints: `<diretorio-local-de-evidencias>/revisoes\T1.diff` … `T12.diff`, `T13-correcoes.diff`. Resultado final: Windows **189 testes, 0 falhas, 2 skips de plataforma** após P0/P1/P2; a última suíte WSL registrada é de **168 testes, 0 falhas, 0 skips**, anterior a essas correções; `run-offline.sh` **PASS em 74 s** no WSL antes delas. Teste real com o modelo 3B no WSL após as correções: intake textual linha a linha, geração e compilação de `Conta.java` concluídas.

**Goal:** Trocar o monólito de resolução por um núcleo determinístico com especificação genérica, perfil declarativo e adaptador Java 8, sem perder nenhum comportamento atual.

**Architecture:** `session.py` vira casca de chat/intake; `core/` contém especificação, regras, orçamento, pipeline e comandos; `adapters/` contém a fronteira de linguagem, com Java 8 como único adaptador real e um stub só de teste. O perfil JSON define linguagem, toolchain, limites e aliases de comando.

**Tech Stack:** Python 3.10+ (sem dependências novas), `unittest`, `javac/java/javap --release 8`, `tarfile`, POSIX sh no empacotamento.

**Spec:** `docs/superpowers/specs/2026-10-23-nucleo-generico-perfil-adaptador-design.md`

## Matriz de execução

| Tarefa | Entrega comprovada | Checkpoint | Verificação no fechamento | Revisão |
|---|---|---|---|---|
| T1 | Perfil declarativo | `T1.diff` | 12 testes de perfil; relacionados verdes | limpa após correções |
| T2 | Especificação genérica e migração de UML | `T2.diff` | suíte com 84 testes, 2 skips | limpa após correções |
| T3 | Protocolos, registry e stub | `T3.diff` | suíte com 89 testes, 2 skips | limpa |
| T4 | Adaptador Java 8 | `T4.diff` | suíte com 106 testes, 2 skips | limpa após correções |
| T5 | Regras genéricas e anti-hard-code | `T5.diff` | suíte com 112 testes, 2 skips | limpa após correções |
| T6 | Orçamento de contexto | `T6.diff` | suíte com 120 testes, 2 skips | limpa após correções |
| T7 | Intake, confiança e plano | `T7.diff` | suíte com 126 testes, 2 skips; inclui `tests/integration/test_intake.py` | limpa após correções |
| T8 | Solver completo e evidências | `T8.diff` | suíte com 143 testes, 2 skips | limpa após correções |
| T9 | Comandos configuráveis e `/perfil` | `T9.diff` | suíte com 150 testes, 2 skips | limpa após correções |
| T10 | Sessão enxuta e regressões | `T10.diff` | suíte com 151 testes, 2 skips | limpa após correções |
| T11 | Cinco enunciados end-to-end | `T11.diff` | suíte com 155 testes, 2 skips | limpa após correções |
| T12 | Empacotamento, documentação e aceitação | `T12.diff` | suíte com 156 testes, 2 skips | limpa após correções |
| T13 | Auditoria, correções e aceitação final | `T13-correcoes.diff` | Windows 168/0/2; WSL 168/0/0; aceitação PASS | correções fechadas |

As contagens intermediárias registram o fechamento de cada tarefa e não substituem o resultado final da T13. Os checkpoints foram preservados fora do repositório conforme a regra desta execução.

## Global Constraints

- Instalação e uso 100% offline; sem API, `sudo`, rede ou pendrive após instalar.
- O diretório de trabalho é a raiz imutável e o limite de escrita; recusar caminho absoluto, `..` e escape por symlink (`workspace/files.py` já faz).
- O modelo não tem shell; só ações allowlisted (`model/actions.py`).
- Java 8: `--release 8`, nomes/tipos/visibilidades/assinaturas/herança exatos do PDF/UML.
- Nenhum nome do fixture (`Frota`, `Hatch`, `Pickup`, `calculaVolume`, `autonomia`) em `src/`.
- Distribuição ≤ 2 GiB; nada de download ou instalação implícita.
- Compilação não prova regra de negócio; nunca afirmar aprovação oficial.
- **Sem commits nesta fase.** Cada tarefa termina com testes verdes e um checkpoint de revisão:
  `git diff -- <arquivos da tarefa>` salvo em `<diretorio-local-de-evidencias>/revisoes\T<N>.diff`.
- Comando de suíte: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests -v`.
- Um módulo por vez durante a tarefa: `python -m unittest tests.unit.test_profile -v`.

## Review Focus

1. **PDF sem UML reconhecível** — o usuário espera uma pergunta e nenhuma escrita; testar em T7/T10.
2. **Arquivo do usuário fora da especificação com erro de compilação** — espera-se diagnóstico e preservação; testar em T8.
3. **Critérios maiores que o orçamento** — espera-se abortar pedindo redução, nunca truncar regra do jurado; testar em T6.
4. **Interface com `implements` e método abstrato** — espera-se validar a assinatura exata, não só compilar; testar em T4/T11.
5. **Caminho de projeto com acento/espaço** — espera-se compilar e executar; testar em T10/T12.

---

## File Structure

Criar:

```text
src/java_assistant/profile.py
src/java_assistant/core/__init__.py
src/java_assistant/core/spec.py
src/java_assistant/core/facts.py
src/java_assistant/core/budget.py
src/java_assistant/core/solver.py
src/java_assistant/core/commands.py
src/java_assistant/adapters/__init__.py
src/java_assistant/adapters/base.py
src/java_assistant/adapters/java8.py
src/java_assistant/adapters/stub.py
packaging/linux/perfil-padrao.json
docs/PERFIL-COMPETICAO.md
tests/unit/test_profile.py
tests/unit/core/test_spec.py
tests/unit/core/test_facts.py
tests/unit/core/test_budget.py
tests/unit/core/test_solver_plan.py
tests/unit/test_no_fixture_leak.py
tests/unit/adapters/test_registry.py
tests/unit/adapters/test_java8.py
tests/unit/test_commands.py
tests/integration/test_intake.py
tests/integration/test_solver.py
tests/integration/test_enunciados.py
tests/fixtures/enunciados/01_heranca/{enunciado.txt,respostas_modelo.json,contrato_esperado.json,casos_execucao.json}
tests/fixtures/enunciados/02_composicao/...
tests/fixtures/enunciados/03_interface/...
tests/fixtures/enunciados/04_entrada/...
tests/fixtures/enunciados/05_regra_aritmetica/...
```

Modificar: `uml/extract.py`, `uml/__init__.py`, `java/toolchain.py`, `java/validator.py`, `session.py`, `criteria.py`, `cli.py`, `config.py`, `review/report.py`, `packaging/linux/assemble_runtime.py`, `packaging/linux/instalar.sh`, `docs/USO-RAPIDO.md`, `docs/ARTEFATOS-LINUX.md`, `tests/acceptance/run-offline.sh`, `tests/acceptance/checklist.md`, `tests/packaging/test_installer.py`, `tests/integration/test_session_flow.py`, `tests/integration/test_pdf_uml.py`, `tests/integration/test_ambiguous_uml.py`, `tests/integration/test_java_toolchain.py`, `tests/unit/test_guided_generation.py`, `tests/unit/test_criteria.py`.

Remover: `src/java_assistant/uml/models.py` (substituído por `core/spec.py`; só depois que todos os imports migrarem, em T2).

---

## Task 1: Perfil declarativo

**Files:** Create `src/java_assistant/profile.py`, `tests/unit/test_profile.py`.

**Interfaces:**
- Produces:
  ```python
  class ProfileError(ValueError): ...

  @dataclass(frozen=True)
  class Limits:
      compile_timeout_s: int = 30
      run_timeout_s: int = 15
      inspect_timeout_s: int = 10
      repair_attempts: int = 2
      max_files: int = 40
      context_tokens: int = 4096
      output_tokens: int = 640

  @dataclass(frozen=True)
  class ContextSettings:
      chars_per_token: float = 3.5
      sections: Mapping[str, int] = ...  # ver default abaixo

  @dataclass(frozen=True)
  class Profile:
      language_id: str
      source_extension: str
      toolchain: Mapping[str, Path]   # "compiler" | "runtime" | "inspector"
      libraries: tuple[Path, ...]
      limits: Limits
      context: ContextSettings
      commands: Mapping[str, tuple[str, ...]]
      origin: str                      # "global" | "project"
      global_path: Path
      project_path: Path | None

  DEFAULT_SECTIONS: Mapping[str, int] = MappingProxyType({
      "protocol": 220, "criteria": 400, "spec_target": 520, "parents": 800,
      "pdf_excerpt": 520, "rules": 300, "memory": 120, "user_request": 180,
  })
  COMMAND_IDS = ("pdf", "undo", "report", "profile", "help", "exit")
  DEFAULT_COMMANDS: Mapping[str, tuple[str, ...]] = MappingProxyType({
      "pdf": ("/pdf",), "undo": ("/desfazer",), "report": ("/relatorio",),
      "profile": ("/perfil",), "help": ("/ajuda",), "exit": ("/sair", "sair"),
  })

  def default_profile(app_home: Path) -> Profile
  def merge_profile(base: dict, override: dict) -> dict
  def load_profile(config: AppConfig, *, app_home: Path,
                   available_adapters: tuple[str, ...]) -> Profile
  def ensure_profile(config: AppConfig, template: Path) -> Path
  def verify_paths(profile: Profile) -> None
  ```
- `load_profile`: lê `config.config_dir/perfil.json` (erro se ausente, com o caminho), mescla `<project_root>/.assistente/perfil.json` quando existir, valida e devolve `origin="project"` nesse caso.
- `default_profile`: mesmo esquema com toolchain `tools/native/bin/{javac,java,javap}`, para testes e CLI antes do template.
- `verify_paths`: erro `ProfileError` nomeando cada caminho inexistente; chamado ao iniciar, antes do primeiro prompt (decisão registrada na Task 13), não na carga.
- Validação: `schema_version == 1`; chave desconhecida → erro listando aceitas; `language.id in available_adapters`; inteiros nas faixas 1–600 (timeouts), 0–5 (`repair_attempts`), 512–8192 (`context_tokens`), 64–2048 (`output_tokens`), `output_tokens < context_tokens`; `2.0 <= chars_per_token <= 6.0`; seções com nomes conhecidos e inteiros > 0; aliases não vazios, únicos entre si, `exit` presente e com ao menos um alias.

- [x] **Step 1: Write the failing tests**

```python
class ProfileTests(unittest.TestCase):
    def test_global_profile_merges_project_override_field_by_field(self):
        # global: limits.repair_attempts=1, commands.pdf=["/pdf"]
        # projeto: limits.repair_attempts=3, commands.pdf=["/enunciado"]
        profile = load_profile(config, app_home=root, available_adapters=("java8",))
        self.assertEqual(3, profile.limits.repair_attempts)
        self.assertEqual(("/enunciado",), profile.commands["pdf"])
        self.assertEqual("project", profile.origin)

    def test_lists_replace_instead_of_concatenating(self): ...
    def test_unknown_key_names_the_accepted_ones(self): ...
    def test_output_tokens_must_be_smaller_than_context(self): ...
    def test_exit_command_is_mandatory(self): ...
    def test_aliases_cannot_collide_across_commands(self): ...
    def test_unknown_language_lists_available_adapters(self): ...
    def test_ensure_profile_preserves_user_edit_and_verify_paths_reports_missing(self): ...
```

- [x] **Step 2: Run and verify failure**

Run: `python -m unittest tests.unit.test_profile -v` → `ModuleNotFoundError: java_assistant.profile`.

- [x] **Step 3: Implement `profile.py`**

Merge recursivo para dicts; lista e escalar substituem. Validação num único `_validate(data, available)`. `load_profile` não verifica existência de toolchain.

- [x] **Step 4: Verify**

Run: `python -m unittest tests.unit.test_profile -v` → PASS. Depois `python -m unittest tests.unit.test_config tests.unit.test_cli -v` → PASS (nada alterado ainda).

- [x] **Step 5: Checkpoint**

Salvar `git diff -- src/java_assistant/profile.py tests/unit/test_profile.py` em `revisoes\T1.diff` e pedir revisão independente (GLM).

---

## Task 2: Especificação genérica e remoção de `uml/models.py`

**Files:** Create `src/java_assistant/core/__init__.py`, `src/java_assistant/core/spec.py`, `tests/unit/core/__init__.py`, `tests/unit/core/test_spec.py`. Modify `uml/models.py` (remover), `uml/__init__.py`, `uml/extract.py`, `java/validator.py`, `tests/integration/test_pdf_uml.py`, `tests/integration/test_ambiguous_uml.py`, `tests/integration/test_java_toolchain.py`, `tests/integration/test_session_flow.py` (imports apenas) — ou manter o shim até T10? **Decisão:** remover agora e atualizar todos os imports; `session.py` acompanha a troca de tipos sem mudar comportamento.

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True, slots=True)
  class Requirement:
      text: str; origin: str; confidence: float; scope: str | None = None

  @dataclass(frozen=True, slots=True)
  class Member:
      name: str; kind: str; type_name: str; visibility: str
      parameters: tuple[tuple[str, str], ...] = ()
      modifiers: tuple[str, ...] = ()

  @dataclass(frozen=True, slots=True)
  class Unit:
      name: str; kind: str; members: tuple[Member, ...]
      modifiers: tuple[str, ...] = ()
      confidence: float = 1.0

  @dataclass(frozen=True, slots=True)
  class Relationship:
      parent: str; child: str; kind: str; confidence: float
      alternatives: tuple[str, ...] = ()

  @dataclass(frozen=True, slots=True)
  class Specification:
      units: tuple[Unit, ...]; relationships: tuple[Relationship, ...]
      requirements: tuple[Requirement, ...]; warnings: tuple[str, ...] = ()
      def to_dict(self) -> dict: ...
      @classmethod
      def from_dict(cls, data: dict) -> "Specification": ...

  def find_unit(spec: Specification, name: str) -> Unit | None
  ```
- `Member.kind ∈ {"field","constructor","method"}`; `Unit.kind ∈ {"class","interface","enum"}`; `Relationship.kind ∈ {"inheritance","implements","association","aggregation","composition","ambiguous"}`; visibilidade `∈ {"public","private","protected","package"}`; confiança `0.0..1.0`; nome `str.isidentifier()`.
- `UmlExtractor.extract(evidence) -> Specification`; aceita `class Nome`, `classe: Nome`, `interface Nome`, sufixos `extends A` e `implements A, B`; mantém `<|--`, `herda de:`, `--`.
- Confiança por origem: `text` → 0.98, `ocr` → 0.80. Requisito por seção: cabeçalho é linha cujo texto normalizado (sem acento/caixa, `:` final removido) é igual ao nome da unidade, ou `classe: Nome`; corpo verbatim até o próximo cabeçalho; preâmbulo vira `scope=None`. Um requisito por seção não vazia.

- [x] **Step 1: Write failing tests**

```python
def test_round_trip_is_stable_and_defensive(self):
    spec = Specification(...)
    self.assertEqual(spec, Specification.from_dict(spec.to_dict()))

def test_rejects_invalid_kind_visibility_name_and_confidence(self): ...
def test_interface_and_implements_are_extracted(self):
    evidence = PdfEvidence("interface Pagavel\n+ pagar(valor: double): boolean\n"
                           "class Boleto implements Pagavel\n", "text", ())
    spec = UmlExtractor().extract(evidence)
    self.assertEqual("interface", find_unit(spec, "Pagavel").kind)
    self.assertEqual(("implements",), {r.kind for r in spec.relationships})

def test_requirements_are_scoped_by_heading_and_preamble_is_general(self): ...
def test_ocr_source_lowers_confidence_to_0_80(self): ...
```

- [x] **Step 2:** `python -m unittest tests.unit.core.test_spec tests.integration.test_pdf_uml -v` → failures.

- [x] **Step 3:** Implement `spec.py`; rewrite `uml/extract.py` to emit `Specification`; update `java/validator.py` to iterate `spec.units`/`members`; delete `uml/models.py`; update imports in `session.py` and the three integration tests. `session.py` keeps behavior: `_contract` type changes, resolução de ambiguidade usa `replace(..., confidence=1.0)`.

- [x] **Step 4:** Run `test_spec`, `test_pdf_uml`, `test_ambiguous_uml`, `test_java_toolchain`, `test_session_flow` → PASS. Resultado observado no fechamento: suíte completa com 84 testes, 0 falhas e 2 skips.

- [x] **Step 5: Checkpoint** `revisoes\T2.diff`.

---

## Task 3: Protocolos de adaptador, registry e stub

**Files:** Create `adapters/__init__.py`, `adapters/base.py`, `adapters/stub.py`, `tests/unit/adapters/__init__.py`, `tests/unit/adapters/test_registry.py`. Modify `java/toolchain.py` (reexport `CompileResult`/`RunResult`), `core/spec.py` (nada além de import).

**Interfaces:**
- Produces:
  ```python
  # adapters/base.py
  from java_assistant.core.facts import Rule, SourceMatchers
  from java_assistant.core.spec import Specification, Unit

  @dataclass(frozen=True)
  class CompileResult: success: bool; diagnostics: str; classes_dir: Path; command: tuple[str, ...]
  @dataclass(frozen=True)
  class RunResult: success: bool; stdout: str; stderr: str; returncode: int | None; timed_out: bool

  class Toolchain(Protocol):
      def compile(self, sources: list[Path], timeout_s: int = 30) -> CompileResult: ...
      def run(self, main_class: str, timeout_s: int, args: tuple[str, ...] = (),
              stdin: str = "") -> RunResult: ...
      def inspect(self, symbol: str, timeout_s: int = 10) -> subprocess.CompletedProcess[str]: ...

  class LanguageAdapter(Protocol):
      id: str
      source_extension: str
      def system_protocol(self) -> str: ...
      def unit_contract(self, spec: Specification, unit: Unit) -> str: ...
      def build_unit_prompt(self, *, spec: Specification, unit: Unit,
                            rules: tuple[Rule, ...], sections: Mapping[str, str]) -> list[Message]: ...
      def parse_unit_source(self, reply: str, unit: Unit) -> str: ...
      def structural_issues(self, spec: Specification, toolchain: Toolchain) -> tuple[str, ...]: ...
      def repair_target(self, diagnostics: str) -> str | None: ...
      def diagnostic_hint(self, diagnostics: str) -> str: ...
      def entry_point(self, spec: Specification) -> str | None: ...
      def matchers(self) -> SourceMatchers: ...

  # adapters/__init__.py
  def adapter_ids(*, allow_stub: bool = False) -> tuple[str, ...]
  def resolve_adapter(adapter_id: str, *, allow_stub: bool = False) -> LanguageAdapter
  ```
- Stub: `id="stub"`, `source_extension=".txt"`, compile sempre `success=True`, run ecoa `stdin`, inspect devolve `CompletedProcess([], 0, "", "")`, `unit_contract` devolve `""`, `entry_point` devolve o primeiro nome, matchers triviais (`r"1\.0"`, `r">"`, `r"super\."`).
- `resolve_adapter("stub")` sem `allow_stub` deve falhar listando `java8`; com `allow_stub=True` resolve.

- [x] **Step 1:** Testes:
```python
def test_stub_is_hidden_by_default_and_listed_when_allowed(self): ...
def test_unknown_adapter_lists_available_ids(self): ...
def test_stub_satisfies_the_protocol_end_to_end(self): ...
def test_java_toolchain_still_exports_result_types(self): ...
```
- [x] **Step 2:** Falha esperada: `ModuleNotFoundError: java_assistant.adapters`.
- [x] **Step 3:** Implementar base/registry/stub; em `java/toolchain.py`, importar e reexportar os dataclasses (remover definições locais).
- [x] **Step 4:** `python -m unittest tests.unit.adapters.test_registry tests.integration.test_java_toolchain tests.integration.test_java_timeout -v` → PASS.
- [x] **Step 5:** Checkpoint `revisoes\T3.diff`.

**Nota:** `adapters/base.py` importa `core.facts`; para T3, crie `core/facts.py` apenas com `Rule` e `SourceMatchers` (Protocol). O corpo das regras chega em T5.

---

## Task 4: Adaptador Java 8

**Files:** Create `adapters/java8.py`, `tests/unit/adapters/test_java8.py`. Modify `session.py` (funções movidas: `_extract_java_source`, `_diagnostic_guidance`, `_ACTION_PROTOCOL`), `java/toolchain.py` (classpath de bibliotecas), `tests/unit/test_guided_generation.py` (migra imports para `adapters.java8`; nomes do fixture permanecem só nos testes).

**Interfaces:**
- Produces:
  ```python
  class Java8Adapter:
      id = "java8"; source_extension = ".java"
      def __init__(self, toolchain: Toolchain | None = None) -> None
      # system_protocol: texto do bloco de ações (write_file/compile/run/respond), sem nomes de exercício
      # unit_contract: declarações exatas da unidade + relacionamentos + cabeçalho extends/implements
      # build_unit_prompt: monta system+user a partir de sections e de unit_contract
      # parse_unit_source: aceita código puro, cerca ```java e <write_file>; exige UMA declaração pública do tipo e nome da unidade
      # structural_issues: usa toolchain.inspect; campo/método/assinatura/herança/implements
      # repair_target: regex r"(?m)([^:\n]+\.java):\d+:\s*error" -> stem
      # diagnostic_hint: int->double, cannot find symbol, missing return, incompatible types
      # entry_point: unidade com Member(kind="method", name="main", modifiers contendo "static")
      # matchers(): JavaMatchers() com factor/guard/super_call
  ```
- `JavaToolchain.__init__(..., classpath: tuple[Path, ...] = ())`; `compile` adiciona `-cp <os.pathsep.join(classpath)>` quando não vazio; `run` usa `classes_dir + classpath`. Teste unitário em `test_java8.py`: `classpath_args` devolve `()` vazio e `("-cp", "a.jar:b.jar")` com duas bibliotecas (usar `os.pathsep` no esperado).
- `build_unit_prompt` inclui, quando houver pai: cabeçalho obrigatório `public class X extends Y` ou `implements`; inclui a frase genérica de construtor vazio quando houver herança sem construtor declarado; inclui `sections["rules"]` sem reescrever texto do PDF.
- `structural_issues` ignora relação com `confidence < 0.9` e `kind == "ambiguous"`; normaliza `abstract` de interfaces antes de comparar assinaturas.

- [x] **Step 1:** Testes (migrados de `test_guided_generation`, sem nomes do fixture):
```python
def test_parses_plain_fenced_and_write_block_single_type(self): ...
def test_rejects_two_public_types_or_wrong_name(self): ...
def test_accepts_public_interface_declaration(self): ...
def test_repair_target_returns_stem_and_none_without_diagnostic(self): ...
def test_entry_point_requires_static_main_member(self): ...
def test_structural_issues_reports_missing_field_signature_and_implements(self): ...
```
- [x] **Step 2:** `python -m unittest tests.unit.adapters.test_java8 -v` → falha.
- [x] **Step 3:** Implementar; remover do `session.py` as três funções movidas e importar de `adapters.java8`.
- [x] **Step 4:** `test_java8`, `test_guided_generation`, `test_session_flow`, `test_pdf_uml` → PASS.
- [x] **Step 5:** Checkpoint `revisoes\T4.diff`.

---

## Task 5: Regras genéricas e teste anti-hard-code

**Files:** Modify `core/facts.py` (corpo completo), `session.py` (remover `_semantic_issues` e `_focused_requirements`), `tests/unit/test_guided_generation.py`, `tests/unit/core/test_facts.py`, create `tests/unit/test_no_fixture_leak.py`.

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class Rule:
      kind: str          # "factor" | "upper_bound" | "super_call"
      unit: str | None
      value: float | None
      text: str          # trecho verbatim do requisito

  class SourceMatchers(Protocol):
      def factor(self, value: float) -> re.Pattern[str]: ...
      def upper_bound_guard(self) -> re.Pattern[str]: ...
      def super_call(self, method: str) -> re.Pattern[str]: ...
      def arithmetic_on_super(self, method: str) -> re.Pattern[str]: ...

  def extract_rules(spec: Specification) -> tuple[Rule, ...]
  def issues(rules: tuple[Rule, ...], unit: Unit, source: str,
             matchers: SourceMatchers) -> tuple[str, ...]
  def prompt_section(rules: tuple[Rule, ...], unit: Unit) -> str
  ```
- Extração a partir de `Requirement.text` verbatim, sem vocabulário de domínio:
  - `aumenta em N%` → fator `1 + N/100`; `reduz em N%` / `reduzida em N%` → `1 - N/100`;
  - `pela metade`/`reduzid... metade` → `0.5`; `dobra` → `2.0`;
  - `reduzid... em um quarto` → `0.75` (nunca `0.25`, que é "reduzida a um quarto");
  - `nunca ... maior que`, `não pode ser maior que` → `upper_bound`;
  - `super_call`: para cada unidade com pai, cada método declarado nos dois; se nenhum requisito do escopo da unidade cita o nome do método → `Rule("super_call", unit, None, method.name)`.
- `issues` só verifica regras cujo `unit` é `None` ou igual ao nome; usa os matchers.
- `prompt_section` gera `"FATOS ARITMÉTICOS OBRIGATÓRIOS:"`, `"LIMITES OBRIGATÓRIOS:"`, `"SOBRESCRITA SEM NOVO EFEITO:"` com os fatores em forma `base * 2.0`.

- [x] **Step 1:** Testes (fixtures com nomes neutros: `Conta`, `Reserva`, `Item`):
```python
def test_percentage_half_double_and_quarter_are_generic(self): ...
def test_quarter_means_three_quarters_remaining(self): ...
def test_upper_bound_requires_a_guard(self): ...
def test_override_rule_forbids_arithmetic_over_super_without_scoped_requirement(self): ...
def test_scoped_requirement_about_method_allows_new_effect(self): ...
def test_prompt_section_uses_only_requirement_text(self): ...
```
`test_no_fixture_leak` varre `src/**/*.py` (`rglob`) e falha se achar `Frota`, `Hatch`, `Pickup`, `calculaVolume` ou `autonomia`.

- [x] **Step 2:** `python -m unittest tests.unit.core.test_facts tests.unit.test_no_fixture_leak -v` → falha (regras ausentes; vazamento presente).
- [x] **Step 3:** Implementar `facts.py`; trocar em `session.py` o prompt específico por `prompt_section(extract_rules(self._spec), unit)`; remover as duas funções heurísticas e a menção "Frota" do protocolo (usar `Main` como exemplo).
- [x] **Step 4:** `test_facts`, `test_no_fixture_leak`, `test_guided_generation`, `test_session_flow` → PASS.
- [x] **Step 5:** Checkpoint `revisoes\T5.diff`.

---

## Task 6: Orçamento de contexto

**Files:** Create `core/budget.py`, `tests/unit/core/test_budget.py`. Modify `criteria.py`, `tests/unit/test_criteria.py`.

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class ContextBudget:
      context_tokens: int = 4096
      output_tokens: int = 640
      chars_per_token: float = 3.5
      sections: Mapping[str, int] = DEFAULT_SECTIONS
      reserved_tokens: int = 128

  @dataclass(frozen=True)
  class BudgetedContext:
      sections: Mapping[str, str]
      omitted: tuple[str, ...]
      truncated: tuple[str, ...]
      available_tokens: int

  class ContextBudgetError(ValueError): ...

  def apply_budget(sections: Mapping[str, str], budget: ContextBudget) -> BudgetedContext
  ```
- `available_tokens = context_tokens - output_tokens - reserved_tokens`.
- Se a soma dos tetos presentes exceder o disponível, descarta seções inteiras nesta ordem: `memory`, `pdf_excerpt`, `parents`, `rules`. Nunca descarta `protocol`, `criteria`, `spec_target`, `user_request`.
- Truncamento no último `\n` antes do teto em caracteres, com `\n[... truncado: N caracteres omitidos]`.
- `criteria` que exceda o teto → `ContextBudgetError("Os critérios gerais excedem ... reduza ...")`.
- `build_context(..., budget: ContextBudget | None = None)` mantém a assinatura atual e usa `apply_budget`; a última mensagem continua sendo `Message("user", user_request)`.

- [x] **Step 1:**
```python
def test_default_4096_budget_fits_all_sections_and_preserves_priority(self): ...
def test_overflow_drops_lowest_priority_first(self): ...
def test_criteria_overflow_aborts_with_actionable_message(self): ...
def test_truncation_cuts_on_line_boundary_and_reports_count(self): ...
def test_build_context_still_places_request_last(self): ...
```
- [x] **Step 2:** Falha: `ModuleNotFoundError`.
- [x] **Step 3:** Implementar; `criteria.build_context` delega ao orçamento.
- [x] **Step 4:** `test_budget`, `test_criteria` → PASS.
- [x] **Step 5:** Checkpoint `revisoes\T6.diff`.

---

## Task 7: Intake, confiança, confirmação e plano

**Files:** Create `core/solver.py` (apenas `ContractStatus`, `classify`, `Plan`, `plan`), `tests/unit/core/test_solver_plan.py`, `tests/integration/test_intake.py`.

**Interfaces:**
- Produces:
  ```python
  class ContractStatus(str, Enum):
      TRUSTED = "trusted"; NEEDS_CONFIRMATION = "needs_confirmation"; NO_CONTRACT = "no_contract"

  def classify(spec: Specification) -> ContractStatus
  def plan(spec: Specification) -> Plan

  @dataclass(frozen=True)
  class Plan:
      order: tuple[str, ...]
      entry: str | None
      issues: tuple[str, ...]
  ```
- `classify`: `NO_CONTRACT` se não há unidades; `NEEDS_CONFIRMATION` se alguma unidade tem `confidence < 0.9`, algum requisito tem `confidence < 0.9`, alguma relação tem `alternatives` ou `confidence < 0.9`, ou alguma unidade tem zero membros; senão `TRUSTED`.
- `plan`: ordem topológica por `inheritance`/`implements` (pai antes), alfabética dentro do mesmo nível; ciclo → `issues=("Ciclo...",)` e ordem alfabética; unidade duplicada → issue. `entry` = unidade com `main` (via `Unit.members`), senão `None`.

- [x] **Step 1:**
```python
def test_no_units_is_no_contract_and_ambiguous_relation_needs_confirmation(self): ...
def test_ocr_confidence_080_needs_confirmation(self): ...
def test_trusted_requires_all_units_confirmed_and_at_least_one_member(self): ...
def test_plan_orders_parent_before_child_and_detects_cycle(self): ...
```
- [x] **Step 2:** Falha.
- [x] **Step 3:** Implementar em `core/solver.py`.
- [x] **Step 4:** `test_solver_plan` → PASS.
- [x] **Step 5:** Checkpoint `revisoes\T7.diff`.

---

## Task 8: Solver completo

**Files:** Modify `core/solver.py`, `review/report.py`; create `tests/integration/test_solver.py`.

**Interfaces:**
- `EvidenceReport` ganha `context_omitted: list[str]` e `observations: list[str]`; `render()` acrescenta `## Contexto omitido (limite de tokens)` e `## Observações de verificação`, com as cinco seções atuais preservadas.
- Produces:
  ```python
  @dataclass(frozen=True)
  class SolveOutcome:
      text: str
      completed: bool

  class Solver:
      def __init__(self, *, spec: Specification, adapter: LanguageAdapter,
                   toolchain: Toolchain, model: ModelLike, workspace: Workspace,
                   history: History, store: ProjectStore, evidence: EvidenceReport,
                   budget: ContextBudget, criteria: str, pdf_text: str = "",
                   memory_summary: str = "", repair_attempts: int = 2,
                   compile_timeout_s: int = 30, run_timeout_s: int = 15,
                   max_files: int = 40) -> None
      def run(self, request: str, *, confirmed_entry: str | None = None) -> SolveOutcome
  ```
- `run`:
  1. `classify` != `TRUSTED` → texto explícito ("Não há contrato confiável... confirme..."), `completed=False`, **zero** chamadas ao modelo e zero compilação.
  2. `len(plan.order) > max_files` → falha explícita antes de qualquer chamada. Gera na ordem do plano; para cada unidade monta seções `protocol|criteria|spec_target|parents|pdf_excerpt|rules|memory|user_request`, chama `apply_budget`, depois `adapter.build_unit_prompt`; grava com `workspace.write` + `history.record`.
  3. `parse_unit_source` inválido → 1 nova tentativa com o erro; depois falha nomeando a unidade.
  4. Compila **todas** as fontes `.java` da raiz. Falha cujo `adapter.repair_target` esteja no plano → regenera até `repair_attempts`; alvo fora do plano → interrompe nomeando o arquivo e **nunca** o reescreve.
  5. `adapter.structural_issues`; se houver, repara a primeira unidade citada até `repair_attempts`.
  6. Executa se `entry_point` existir, com `run_timeout_s`; falha/timeout → `completed=False` com saída.
  7. `completed=True` e texto `Solução concluída: ...` somente após compilação **e** validação estrutural (quando houve spec) **e** execução aprovada quando há entrada. Registra `"<arquivo> sha256=<hex>"` em `evidence.compiled`, `BudgetedContext.omitted/truncated` em `evidence.context_omitted`, e as observações (contrato ausente, arquivo não gerado pelo assistente, entrada não executada) em `evidence.observations`.

- [x] **Step 1:** Testes:
```python
def test_no_contract_asks_for_confirmation_without_model_call_or_compile(self): ...
def test_trusted_contract_generates_in_dependency_order_and_compiles(self): ...
def test_foreign_file_diagnostic_is_reported_and_never_rewritten(self): ...
def test_repair_is_bounded_by_repair_attempts(self): ...
def test_more_units_than_max_files_fails_before_model_call(self): ...
def test_completion_requires_execution_when_entry_exists(self): ...
def test_two_runs_produce_identical_evidence_and_hashes(self): ...
def test_report_separates_omitted_context_and_observations(self): ...
```
- [x] **Step 2:** Falha.
- [x] **Step 3:** Implementar; `session.py` ainda não usa (T10).
- [x] **Step 4:** `python -m unittest tests.integration.test_solver -v` → PASS; módulos do solver/plan/adapters também.
- [x] **Step 5:** Checkpoint `revisoes\T8.diff`.

---

## Task 9: Comandos configuráveis e `/perfil`

**Files:** Create `core/commands.py`, `tests/unit/test_commands.py`. Modify `session.py` (só o mapa de comandos e o novo handler), `cli.py` (mensagem de ajuda), `review/report.py` (nada ainda).

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class CommandRegistry:
      aliases: Mapping[str, str]          # alias normalizado -> id
      @classmethod
      def from_profile(cls, commands: Mapping[str, tuple[str, ...]]) -> "CommandRegistry": ...
      def resolve(self, text: str) -> str | None
      def help_text(self) -> str
  ```
- `resolve` normaliza `casefold` + `strip`; aliases são comparados como texto literal. `help_text` lista somente aliases ativos, na ordem `pdf, undo, report, profile, help, exit`.
- `/perfil` mostra: caminho global, caminho de projeto (ou "nenhum"), origem, `language.id`, limites e aliases; nunca imprime conteúdo de arquivo nem caminho de pendrive.

- [x] **Step 1:**
```python
def test_resolves_renamed_and_disabled_commands(self): ...
def test_unknown_command_returns_none_and_help_lists_only_active_aliases(self): ...
def test_help_text_is_generated_from_profile_order(self): ...
```
- [x] **Step 2:** Falha.
- [x] **Step 3:** Implementar e ligar em `session.handle`: `command = self.commands.resolve(stripped)`; `exit/help/profile/pdf/undo/report` mapeados; `None` cai no fluxo atual.
- [x] **Step 4:** `test_commands`, `test_session_flow` → PASS.
- [x] **Step 5:** Checkpoint `revisoes\T9.diff`.

---

## Task 10: Sessão enxuta e regressões migradas

**Files:** Modify `session.py` (grande), `cli.py`, `tests/integration/test_session_flow.py`, `tests/integration/test_ambiguous_uml.py`, `tests/unit/test_cli.py`.

**Interfaces:**
- `AssistantSession.__init__(..., profile: Profile | None = None, adapter: LanguageAdapter | None = None)`; omitidos → `default_profile(Path(os.environ.get("JAVA_ASSISTANT_HOME", ".")))` e `resolve_adapter(profile.language_id)`. `toolchain` continua obrigatório.
- `session.handle`:
  1. comando via registry;
  2. escolha de PDF pendente;
  3. ambiguidades pendentes (mesma semântica);
  4. pedido de geração **com** `Specification` → `Solver(...).run` (só se `classify` for `TRUSTED`; senão mensagem de confirmação sem modelo);
  5. demais pedidos → loop de ações atual, inalterado, com `_ACTION_PROTOCOL` vindo de `adapter.system_protocol()`.
- Remover: `_semantic_issues`, `_focused_requirements`, `_generation_messages`, `_generate_one_class`, `_guided_solve`, `_required_java_names`, regex de `(main)`. Manter: `_relevant_files`, `_focused_relevant_files`, `_execute_action`, `_chat` (com limites do perfil: 12 ações, 3 falhas), `_list_pdfs`, `_select_pdf`, `_ambiguity_question`, `_resolve_ambiguity`.
- `_missing_java_names` → `_missing_units() -> list[str]` (unidades de `plan(spec).order` sem `<Nome><extensão>` na raiz). No loop de ações, a etapa obrigatória usa `adapter.unit_contract(spec, unit)` em vez de `_focused_requirements`.
- `_main_class_name` → `adapter.entry_point(self._spec)`; o loop usa `adapter.source_extension` no lugar de `.java`.
- `cli.main` passa a: `ensure_profile(config, app_home/"share"/"perfil-padrao.json")`, `load_profile(..., available_adapters=adapter_ids())`, `verify_paths(profile)`, `JavaToolchain(config.project_root, javac=profile.toolchain["compiler"], java=profile.toolchain["runtime"], javap=profile.toolchain["inspector"], classpath=profile.libraries)`, `AssistantSession(..., profile=profile, adapter=resolve_adapter(profile.language_id))`.

- [x] **Step 1:** Atualizar as fixtures de teste para criar o perfil:
```python
def profile_for(root: Path) -> Profile:
    return replace(default_profile(root), commands=DEFAULT_COMMANDS)
```
Cada teste existente mantém a asserção; nenhum teste é apagado. Duas fixtures mudam de forma, não de intenção:
- `test_ambiguous_uml`: as classes ganham um membro (`+ id: int`) para que, resolvida a ambiguidade, a especificação seja `TRUSTED`; a regressão (bloqueio até a escolha) continua idêntica.
- `test_main_prompt_does_not_inherit_arithmetic_rules_from_other_classes`: a unidade de teste declara `+ main(args: String[]): void` no UML; não se usa mais `classe X (main)` no texto.
- [x] **Step 2:** Rodar `test_session_flow` → falha de assinatura/atributo.
- [x] **Step 3:** Implementar a casca; preservar exatamente as mensagens testadas (`"Solução concluída"` só no caminho do solver).
- [x] **Step 4:** `test_session_flow`, `test_ambiguous_uml`, `test_cli`, `test_criteria` → PASS. Suíte completa verde.
- [x] **Step 5:** Checkpoint `revisoes\T10.diff`.

---

## Task 11: Cinco enunciados distintos end-to-end

**Files:** Create `tests/integration/test_enunciados.py` e as cinco fixtures. Nenhum código de produto novo, exceto correções que os testes revelarem.

**Formato da fixture**

```json
// respostas_modelo.json
{"Ordem": ["Conta.java", "Conta.java"], "Conta": ["resposta_invalida", "fonte_valida"]}
```

- `enunciado.txt`: texto do PDF (texto puro).
- `respostas_modelo.json`: fila de respostas por unidade; `"reparo"` é qualquer resposta que force uma regeneração.
- `contrato_esperado.json`: `{"units": [...], "relationships": [...]}`.
- `casos_execucao.json`: `{"entry": "X", "stdin": "...", "stdout_contains": [...]}` ou `{}`.

**Cenários:** herança/polimorfismo (`Forma`, `Circulo`, `Retangulo`, `Desenho`); composição (`Time`, `Jogador`); interface (`Pagavel`, `Boleto`, `Cartao`); entrada/saída (`ConversorTemperatura` com `Scanner`); regra aritmética com limite (`Bonus`, fator 1.5, teto, exceção). Cada um cobre feliz + um reparo + um negativo que deve falhar honestamente.

- [x] **Step 1:** Teste parametrizado que, para cada fixture: monta projeto temporário, `FixedExtractor`, `UmlExtractor`, `Solver` com `ScriptedModel`, compila com `JavaToolchain`, executa quando há `casos_execucao.json`, compara contrato e saída. No caminho negativo: `outcome.completed is False` e `"Solução concluída" not in outcome.text`.
- [x] **Step 2:** Rodar → falhas por fixtures ausentes.
- [x] **Step 3:** Criar fixtures e corrigir somente defeitos genéricos comprovados.
- [x] **Step 4:** `python -m unittest tests.integration.test_enunciados -v` → PASS em Windows (javac disponível) e registrar skip explícito se `javac` faltar.
- [x] **Step 5:** Checkpoint `revisoes\T11.diff`.

---

## Task 12: Empacotamento, documentação e aceitação

**Files:** Create `packaging/linux/perfil-padrao.json`, `docs/PERFIL-COMPETICAO.md`. Modify `packaging/linux/assemble_runtime.py`, `packaging/linux/instalar.sh`, `tests/packaging/test_installer.py`, `tests/acceptance/run-offline.sh`, `tests/acceptance/checklist.md`, `docs/USO-RAPIDO.md`, `docs/ARTEFATOS-LINUX.md`.

**Interfaces:**
- `perfil-padrao.json` = saída de `default_profile(...)` menos caminhos absolutos; contém `schema_version`, `language`, `toolchain`, `libraries`, `limits`, `context`, `commands`.
- `assemble_runtime.py`: `required_paths` inclui `packaging/linux/perfil-padrao.json`; adiciona em `share/perfil-padrao.json`.
- `instalar.sh`: após os critérios, `if [ ! -f "$APP_CONFIG/perfil.json" ]; then cp "$RELEASE/share/perfil-padrao.json" "$APP_CONFIG/perfil.json"; fi`.
- `test_installer.make_bundle` passa a incluir `share/perfil-padrao.json`; teste edita o perfil e verifica preservação na reinstalação; teste de texto exige ausência de rede/sudo e presença do bloco de cópia.
- `run-offline.sh`: após a instalação, exige `$XDG_CONFIG_HOME/java-assistente/perfil.json`; edita o arquivo, reinstala, exige conteúdo preservado.
- Docs: comandos e aliases, precedência do perfil, `/perfil`, limites e a declaração explícita de que UML visual não é interpretado.

- [x] **Step 1:** Atualizar `test_installer` (falha: perfil ausente no bundle de teste).
- [x] **Step 2:** Implementar empacotamento.
- [x] **Step 3:** `python -m unittest tests.packaging.test_installer -v` → PASS (execução do shell é skip no Windows, texto roda).
- [x] **Step 4:** Escrever `docs/PERFIL-COMPETICAO.md` e ajustar os outros docs.
- [x] **Step 5:** Checkpoint `revisoes\T12.diff`.

---

## Task 13: Verificação final e limitações

**Files:** Modify `docs/superpowers/plans/2026-10-23-nucleo-generico-perfil-adaptador.md` (registro de execução), `docs/USO-RAPIDO.md` (se a verificação revelar ajuste).

- [x] **Step 1: Suíte completa**

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests -v
```
Esperado: todos PASS; skips de plataforma contados e nomeados.

- [x] **Step 2: Repetibilidade** — rodar `tests.integration.test_enunciados` duas vezes; comparar os hashes de evidência registrados; devem ser idênticos.

- [x] **Step 3: Anti-hard-code** — `python -m unittest tests.unit.test_no_fixture_leak -v` → PASS.

- [x] **Step 4: Bundle e aceitação (se o ambiente permitir)**

```sh
bash packaging/linux/build-bundle.sh
bash tests/acceptance/run-offline.sh dist/java-assistente-linux-x86_64
```
Esperado: bundle ≤ 2 GiB; perfil criado e preservado; PASS. Registrar se foi WSL ou Mint real.

- [x] **Step 5: Registro final** — anexar ao plano: comandos, contagem PASS/FAIL/skip, falhas ambientais, e as limitações: UML visual não implementado, testes dos jurados indisponíveis, qualidade do modelo 3B não medida no hardware da competição, estimativa de tokens heurística, segunda linguagem não validada e hardware Mint pendente.

### Registro de execução (2026-10-23 a 2026-10-24)

**Suíte completa** (Windows, Python 3.14.5, `javac`/`javap` reais):

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests -v
```

Resultado final após as correções da auditoria: **168 testes, 0 falhas, 2 skips** (`Ran 168 tests`, `OK (skipped=2)`). Skips nomeados:

- `packaging.test_installer.InstallerTests.test_install_and_update_preserve_criteria_and_state` — execução real do instalador reservada ao Linux.
- `unit.workspace.test_files.WorkspaceTests.test_rejects_symlink_that_escapes_root` — Windows sem privilégio de criar symlink (`WinError 1314`).

**Suíte completa no Linux (WSL Ubuntu 24.04, Python 3.12.3, JDK 17 e tesseract 5.5.3 do bundle):** **168 testes, 0 falhas, 0 skips**. Os dois skips de Windows passaram: instalador real (`test_install_and_update_preserve_criteria_and_state`) e symlink de escape (`test_rejects_symlink_that_escapes_root`). OCR real verificado à parte: PDF só-imagem montado com `pdftoppm` + `tiff2pdf` do bundle; `PdfExtractor` com os binários do bundle retornou `source=ocr` e recuperou `class Veiculo`, `- placa: String`, `class Carro` e `Veiculo herda de Carro`.

**Fluxo no app instalado (WSL, bundle final):** projeto `.../Projeto com acento á` com `Enunciado da prova á.pdf`; `/pdf` → `1` respondeu `PDF carregado. Classes reconhecidas: Veiculo, Carro`; `/perfil` mostrou origem global e limites (`contexto 4096`, `saída 640`, `reparos 2`, `arquivos 40`). O modelo respondeu em português a uma pergunta comum. Durante a execução, `ss` mostrou `llama-server` escutando apenas em `127.0.0.1` e a única conexão estabelecida era `python3` ↔ `llama-server`. Pico somado de RSS (`llama-server` + `python3`): **2.533.184 KiB (~2,42 GiB)**, sem swap.

**Repetibilidade:** os cinco enunciados rodaram duas vezes cada em projeto temporário novo; os SHA-256 das fontes geradas foram idênticos nas duas execuções em todos os cenários (`formas`, `composicao`, `interface`, `entrada_saida`, `bonus`).

**Anti-hard-code:** `python -m unittest tests.unit.test_no_fixture_leak -v` → PASS (1 teste).

**Bundle e aceitação (WSL Ubuntu 24.04):**

```sh
ARTIFACTS_DIR=<checkout original>/artifacts/linux-x86_64 OUTPUT_DIR=$HOME/t13-bundle bash packaging/linux/build-bundle.sh
cd $HOME/t13-bundle && sha256sum -c manifest.sha256
```

- Bundle criado: **1.929.786.362 bytes** antes das correções e **1.929.787.220 bytes** após as correções da auditoria (ambos abaixo do limite de 2 GiB); `runtime.tar.gz: OK`, `model.gguf: OK` nas duas versões.
- Instalação com o bundle novo e `JAVA_ASSISTANT_NO_START=1`: `perfil.json` criado e byte a byte igual a `share/perfil-padrao.json`; após editar `repair_attempts` e reinstalar, o valor editado permaneceu.
- `tests/acceptance/run-offline.sh` **passou** no WSL em 2026-10-24 com o bundle final: `PASS: inicialização offline após remover a origem em 74 s`. As tentativas anteriores falharam por espaço no host, não pelo artefato: o `C:` estava com 1,8 GB livres, o VHD é dinâmico e o ext4 entrava em `emergency_ro` (`/dev/sdd ... emergency_ro`) durante a escrita de ~5 GB, derrubando a VM com `0xC0000374`. Não era RAM: a VM tinha 4,4-7,3 GB livres e o `llama-server` com os mesmos argumentos do app (modelo 3B, `--ctx-size 4096`, 2 threads) subia sozinho. Depois de remover dados de teste do guest e caches, o host ficou com 40,5 GB livres e o teste passou. O script agora imprime a saída e o código do instalador quando ele falha.

**Auditoria final e correções:** uma auditoria independente apontou oito defeitos; todos foram corrigidos com testes de regressão: (1) `_chat` bloqueia contrato não confiável sem chamar o modelo; (2) ciclo de herança não trava `_focused_relevant_files`; (3) limites do perfil chegam a runtime, transporte HTTP, orçamento de contexto e timeouts do loop de ações; (4) aviso de solução não verificada deriva de ações realmente concluídas; (5) validador e prompt preservam `static`; (6) entrada ambígua é escolhida pelo nome no pedido, com fronteira de palavra; (7) extensão do perfil precisa coincidir com o adaptador; (8) `inspect_timeout_s` é aplicado. A revisão final limitada foi feita com `mimo-v2.6-flash-free` porque o modelo GLM gratuito atingiu o limite de uso; os achados comprováveis dessa revisão também foram corrigidos (flags de verificação, teste discriminador da confirmação pendente, timeouts do loop de ações, alinhamento da spec e evidência do checklist).

**Desvio consciente:** `cli.main` chama `verify_paths(profile)` ao iniciar, antes do primeiro prompt. Falha cedo e nomeia o caminho; a documentação (`docs/PERFIL-COMPETICAO.md`) e a spec (§7.3 e §19) foram alinhadas a esse comportamento.

**Limitações desta entrega:**

- UML visual (caixas, setas, posições) não é interpretado; só texto e notação textual de classes, membros e herança.
- Testes dos jurados continuam indisponíveis: compilação e validação estrutural não provam regra de negócio.
- No bundle final, o modelo 3B respondeu a uma pergunta comum no WSL, mas a geração e execução completas de um enunciado não foram repetidas; a evidência completa disponível é anterior à reconstrução final.
- Orçamento de tokens é estimativa heurística (`chars_per_token`), não contagem do tokenizador.
- Apenas o adaptador Java 8 é validado; uma segunda linguagem não foi testada.

### Registro de execução — correções P0/P1/P2 (2026-10-25)

Defeitos confirmados por leitura de código antes das correções:

- **P0 — intake textual ausente:** PDF sem UML reconhecível (ou classe incompleta) bloqueava sem aproveitar a resposta do usuário; não havia como completar o contrato textualmente antes de gerar.
- **P1 — requisito longo truncado:** regra importante no fim de um enunciado extenso podia cair fora de `pdf_excerpt` e nunca chegava ao modelo.
- **P2 — execução superestimada:** solução sem entrada era apresentada como se a execução provasse o comportamento; o caso `Scanner` não distinguia smoke test de validação funcional.

Correções implementadas com teste antes do código:

- Intake textual em `session.py`: com um PDF selecionado, a resposta do usuário é interpretada pelo `UmlExtractor`, fundida ao contrato do PDF, reclassificada e tem ambiguidades recalculadas; nenhuma chamada ao modelo, escrita ou compilação ocorre antes de o contrato ficar `trusted`. Unidade do usuário sem membros não apaga membros do PDF; correção parcial preserva os membros e as relações não citados; requisitos são deduplicados por `(text, scope)` e, no mesmo escopo, a evidência do usuário prevalece sobre a do PDF. Uma resposta textual com unidades também resolve a ambiguidade sem exigir o número da opção.
- Origem `user` em `uml/extract.py` com confiança `0,98`; `ocr` continua `0,80`. Requisitos mantêm evidência de origem distinta (`pdf-text` vs. texto do usuário).
- `requirements_section` em `core/facts.py` monta o texto dos requisitos aplicáveis (escopo da unidade primeiro, geral depois) e o anexa ao contrato UML da unidade dentro da seção protegida `spec_target` do `Solver._generate_unit`; o contrato vem primeiro para não ser truncado. Não há aumento de contexto nem heurística de domínio.
- Execução sem caso explícito é rotulada como **smoke test sem entrada/saída verificada** em evidência, observações e resultado; falha de execução continua falha. `completed=True` exige compilação e validação estrutural, e a ausência de verificação funcional fica explícita.

Comando da suíte completa (Windows, Python 3.14.5):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests -v
```

Resultado: **189 testes, 0 falhas, 2 skips** (`Ran 189 tests in 123.153s`, `OK (skipped=2)`). Os dois skips são os mesmos de plataforma já registrados (instalador real no Windows e symlink com `WinError 1314`). Módulos afetados rodados antes: `test_intake`, `test_ambiguous_uml`, `test_solver`, `test_facts` → **43 testes, 0 falhas**. `git diff --check` sem erros de whitespace.

Testes novos (21): `tests/integration/test_intake.py` (15: sem contrato → texto constrói contrato; unidade incompleta → correção textual completa; correção inválida continua bloqueando; nenhum modelo/escrita/compilação antes de `trusted`; confirmação simples não inventa membros; sem loop de pergunta repetida; intake confiável chega ao solver; unidade do usuário sem membros não apaga os do PDF; correção parcial preserva membros não citados; relação não citada sobrevive; regra do usuário substitui a do PDF no mesmo escopo; outro tipo de relação do mesmo filho sobrevive; sobrecargas não colidem por nome; texto digitado linha a linha é aplicado na linha vazia; `run_java` no chat é rotulado como smoke test), correção textual resolve ambiguidade sem número em `test_ambiguous_uml.py`, origem/confiança `user` em `test_pdf_uml.py`, `requirements_section` em `test_facts.py`, requisito longo em seção protegida e smoke test em `test_solver.py`, regressão `Scanner` em `test_enunciados.py`.

**Revisão QA independente (MiMo-V2.6-Flash Free, somente leitura):** confirmou 185/0/2 por execução própria e apontou nove achados. Corrigidos com teste: união de membros em correção parcial; `run_java` do chat agora registra observação e texto de smoke test; resposta textual com unidades resolve ambiguidade sem número; relação não citada sobrevive à correção; asserções negativas tautológicas trocadas por invariantes positivos; texto de confirmação só afirma estrutura confirmada quando o contrato ficou `trusted`; enumeração e escopo do registro ajustados. O risco inverso de truncamento (`spec_target`) ficou documentado. Nenhum achado ficou aberto.

**Revisão crítica final (DeepSeek V4.1 Flash 1017, somente leitura):** confirmou 188/0/2 por execução própria. Achados materiais corrigidos com teste: (1) regra do usuário agora substitui a do PDF no mesmo escopo, em vez de exigir os dois fatores; (2) `spec_target` monta primeiro o contrato UML da unidade e depois os requisitos, para que o contrato não seja cortado; (3) a correção só substitui relações do mesmo tipo e mantém `implements`/outros tipos não recitados; (4) sobrecargas de método usam tipos de parâmetro como identidade; (5) resposta final do chat avisa que `run_java` sem entrada foi smoke test. Também foram ajustados o rótulo `REQUISITOS APLICÁVEIS`, o registro de classes de origem `user` em `/relatorio` e a limitação de truncamento. Unidade duplicada em contrato não confiável continua colapsando na fusão; é um caso de baixo risco e não foi alterado.

**Teste real com modelo 3B (WSL Ubuntu 24.04, após P0/P1/P2):** bundle reconstruído a partir desta worktree com os artefatos já existentes: **1.929.789.336 bytes**, `runtime.tar.gz: OK`, `model.gguf: OK`. Projeto de teste com PDF mínimo `class Conta` (sem membros). A correção foi digitada **linha a linha** (`class Conta`, `+ total(): double`, regra geral) e aplicada na linha vazia; o app respondeu `Contrato atualizado com a resposta textual. Agora posso gerar o código.` Em seguida, `Resolva` produziu `Solução concluída: 1 arquivo(s) gerado(s) e compilados; nenhuma entrada executada.` O `Conta.java` compilado teve SHA-256 `2b15053de7b56638b6d722c4d6ac32ebfc3d5d37defbbdefcdb1f56b7e2f16e0`. O `/relatorio` registrou `Conta.java` em **Compilado**, nada em **Testado localmente**, o truncamento de `protocol` e `Entrada não executada: nenhuma unidade com main estático no contrato`. O fonte gerado incluiu campo e construtor privados não previstos no contrato; a validação estrutural aceitou e a compilação passou. Isso comprova o fluxo real de intake, geração e compilação, **não** execução nem regra de negócio.

**Limitações residuais destas correções:**

- O contrato UML da unidade vem primeiro em `spec_target`; os requisitos vêm depois. Se o conjunto exceder o teto, o requisito (inclusive uma regra longa) pode ser truncado, e `context_omitted` registra isso. Um contrato de unidade sozinho acima do teto ainda pode ser cortado.
- A validação estrutural atual garante os membros exigidos, mas não rejeitou campo/construtor extras gerados pelo modelo 3B no teste real.
- O teste real não executou o programa gerado (a unidade não tinha `main`); ele não prova entrada/saída nem regra de negócio.

### Gates externos pendentes

- [ ] **Linux Mint real em máquina CPU-only de 4–6 GB:** medir inicialização, pico de RAM e comportamento do modelo no ambiente-alvo.
- [ ] **USB 2.0 e hardware da competição:** medir cópia/instalação e confirmar o uso offline após instalar.

Esses gates exigem hardware indisponível nesta sessão. O WSL comprova o pacote Linux e o fluxo offline, mas não substitui essas medições.

---

## Dependências e ordem

```text
T1 ─┬─> T6 ─┐
T2 ─┼─> T3 ─> T4 ─> T5 ─┐
    └─> T7 ──────────────┼─> T8 ─> T10 ─> T12 ─> T13
T1 ─────> T9 ────────────┘
T8 ─> T11 ─────────────────────────> T12
```

T1–T9 não alteram o comportamento observável da sessão, exceto T5 (remove heurísticas) e T9 (aliases). A suíte completa deve ficar verde ao fim de cada tarefa.

## Mapa spec → tarefas

| Seção da spec | Tarefa |
|---|---|
| 7.2 especificação genérica | T2 |
| 7.3 perfil | T1, T12 |
| 7.4 pipeline | T7, T8 |
| 7.5 regras genéricas | T5 |
| 7.6 orçamento | T6 |
| 7.7 adaptadores | T3, T4 |
| 7.8 comandos | T9 |
| 7.9 evidências | T8, T12 |
| 7.10 recuperação/repetibilidade | T8, T13 |
| 11 cinco enunciados | T11 |
| 12 regressões | T10, T11, T12 |
| 16 critérios de aceitação | T13 |
