# Fidelidade ao Enunciado Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o assistente transformar um enunciado (texto colado ou PDF) nas classes Java pedidas, com nomes, tipos, visibilidades, heranca e regras de negocio corretos, sem exigir classe `main` e sem decorar nenhum exercicio.

**Architecture:** Uma unica entrada de enunciado (texto colado ou PDF) produz o mesmo contrato `JavaContract` ja existente; o contrato alimenta um gerador que escreve uma classe por vez, compila com `--release 8`, confere assinaturas por `javap` e valida comportamento por um arnes gerado que instancia as classes e chama os metodos, como um juiz externo faria. Nada de comportamento de dominio fica no produto: os exercicios conhecidos viram fixtures.

**Tech Stack:** Python 3.10+ (somente biblioteca padrao), `unittest`, `javac`/`javap`/`java` (JDK empacotado), `pdftotext`/`pdftoppm`/`tesseract`, `llama.cpp` + Qwen2.5-Coder-3B GGUF.

**Spec:** `docs/superpowers/specs/2026-10-21-assistente-java-offline-design.md` (secoes 3.3, 4, 7, 8 e 11). Memoria portatil: `docs/superpowers/specs/2026-10-22-memoria-portatil-entre-sessoes-design.md`.

## Global Constraints

- Operacao 100% offline, sem API, `sudo`, rede ou dependencia externa.
- Python 3.10+ e biblioteca padrao apenas; nenhuma dependencia nova em `pyproject.toml`.
- Codigo Java gerado compativel com Java 8 (`javac --release 8`).
- A pasta de trabalho e a raiz imutavel e o limite de escrita; caminhos absolutos, `..` e symlink de escape sao recusados.
- O modelo nao tem shell: so executa acoes validadas da allowlist em `model/actions.py`.
- Nenhum nome, formula ou regra de exercicio concreto em `src/`. Exercicios vivem em `tests/fixtures/`.
- Compilar e testar localmente nao prova aprovacao dos jurados; o relatorio nunca afirma isso.
- Classes de teste nunca ficam na pasta de entrega.
- `CRITERIOS_GERAIS.md` continua editavel pelo usuario e preservado em reinstalacao.

## Review Focus

- **Assinatura com tipo boxed errado** (`Double` gerado como `double`): o validador quebra com `NoSuchMethodError` e o resultado e zero, mesmo com a formula certa. Teste em Task 8.
- **Construtor sem os campos herdados** (`Hatch(int,int,Double,boolean,int)`): o validador nao instancia a classe. Teste em Task 8.
- **Efeito da superclasse aplicado duas vezes ou nenhuma** (`Pickup` auto + carga total = 500x0,90x0,50 = 225): silencioso, compila, erra o numero. Teste em Task 8.
- **Resposta do modelo cortada no meio** e tratada como erro de sintaxe, escondendo a causa. Teste em Task 4.
- **Enunciado sem a palavra `class`** (lista, tabela, texto corrido) produz contrato vazio e o gerador tenta compilar nada. Teste em Task 6.

---

## File Structure

- `src/java_assistant/session.py` — orquestracao; recebe entrada de texto, perde o hardcode do Frota, passa a exigir contrato nao vazio.
- `src/java_assistant/cli.py` — fronteira de erro; `/enunciado` no laco de conversa.
- `src/java_assistant/model/client.py` — teto de tokens por chamada e deteccao de resposta cortada.
- `src/java_assistant/uml/extract.py` — extrator tolerante a variacoes de enunciado e a layout com coordenadas.
- `src/java_assistant/pdf/extract.py` — passa a devolver coordenadas das palavras do OCR.
- `src/java_assistant/java/toolchain.py` — limpeza do diretorio de classes e execucao de classes Java arbitrarias.
- `src/java_assistant/java/judge.py` (novo) — gera o arnes de comportamento a partir das regras do contrato e roda como juiz.
- `src/java_assistant/review/report.py` — preenche "nao comprovado" de verdade.
- `tests/fixtures/enunciados/` — E1..E4 em texto e PDF, com contrato esperado em `.json`.
- `tests/fixtures/frota/` — copia do desafio real: `Heranca e Polimorfismo III.pdf`, `Frota.class`, `Frota$1.class`, `Classes de teste/`.
- `tests/qualidade/medir.py` — medidor de fidelidade (nao roda na suite padrao).
- `tests/acceptance/qualidade.md` — linha de base e comparacao.
- `tests/acceptance/validator.sh` — roda o validador real contra a solucao gerada.

### Ordem de execucao

| Fase | Tarefas | Por que nesta ordem |
|---|---|---|
| 0 | 0, 1, 2 | Sem commit limpo e sem regua nao ha como medir nada |
| 1 | 3, 4 | Falhas que aparecem na frente do usuario |
| 2 | 5, 6, 7 | Entender o enunciado antes de gerar |
| 3 | 8 | O coracao: acertar o comportamento |
| 4 | 9, 10, 11, 12 | Corrigir sem estragar, e medir de novo |

---

### Task 0: Preservar o trabalho nao commitado

**Files:**
- Modify (stage only): os 24 arquivos ja modificados
- Add: `AGENTS.md`, `packaging/linux/assemble_runtime.py`, `tests/unit/test_guided_generation.py`

**Interfaces:**
- Consumes: nada
- Produces: arvore limpa para as tarefas seguintes

- [ ] **Step 1: Registrar o diff atual**

Run: `git status --short; git diff --stat`
Expected: 24 modificados, 3 novos. Guardar a saida.

- [ ] **Step 2: Rodar a suite antes de commitar**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests`
Expected: `OK (skipped=2)`

- [ ] **Step 3: Commitar em dois commits separados**

```bash
git add AGENTS.md packaging/linux/assemble_runtime.py tests/unit/test_guided_generation.py
git commit -m "docs: add agent guidance for offline build"
git add -u
git commit -m "feat: harden guided generation and bundle assembly"
```

### Task 1: Enunciado colado em texto

**Files:**
- Modify: `src/java_assistant/session.py`
- Modify: `src/java_assistant/cli.py`
- Modify: `src/java_assistant/review/report.py`
- Test: `tests/integration/test_session_flow.py`, `tests/unit/test_cli.py`

**Interfaces:**
- Consumes: `PdfEvidence(text, source, warnings)`, `UmlExtractor().extract(evidence) -> JavaContract`
- Produces: comando `/enunciado` (inicia a captura) e `/fim` (encerra); a captura segue exatamente o caminho de `_select_pdf`

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_pasted_text_enunciado_produces_same_contract_as_pdf(self):
    session.handle("/enunciado")
    session.handle("CLASSE: Conta\n- saldo: int\n+ Conta(int)")
    reply = session.handle("/fim")
    self.assertIn("Conta", reply.text)
    self.assertEqual([c.name for c in session._contract.classes], ["Conta"])

def test_pasted_text_without_classes_asks_instead_of_generating(self):
    session.handle("/enunciado")
    session.handle("texto qualquer sem diagrama")
    reply = session.handle("/fim")
    self.assertIn("não reconheci", reply.text)
    self.assertIsNone(session._contract)

def test_paste_mode_is_cancelled_by_sair(self):
    session.handle("/enunciado")
    reply = session.handle("/sair")
    self.assertTrue(reply.exit_requested)
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest tests.integration.test_session_flow -v`
Expected: FAIL — o comando `/enunciado` cai no chat comum.

- [ ] **Step 3: Implementar a captura em `session.py`**

`handle()` ganha dois ramos antes do despacho normal: `_awaiting_pdf_choice` ja existe como precedente — usar o mesmo padrao com `_awaiting_enunciado: bool` e `_enunciado_lines: list[str]`. `/fim` monta `PdfEvidence(text="\n".join(lines), source="texto colado", warnings=())` e chama o mesmo `UmlExtractor` que `_select_pdf` usa; extrair o trecho comum de `_select_pdf` para `_apply_evidence(evidence, label)`.

- [ ] **Step 4: Rodar os testes**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest tests.integration.test_session_flow tests.unit.test_cli -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/java_assistant/session.py src/java_assistant/cli.py src/java_assistant/review/report.py tests/
git commit -m "feat: accept pasted enunciado as text input"
```

### Task 2: Regua de fidelidade

**Files:**
- Create: `tests/fixtures/enunciados/E1.txt`..`E4.pdf`, `tests/fixtures/enunciados/expected/*.json`
- Create: `tests/fixtures/frota/` (copia do desafio real)
- Create: `tests/qualidade/medir.py`
- Create: `tests/acceptance/qualidade.md`

**Interfaces:**
- Consumes: `AssistantSession`, `JavaToolchain`, `ContractValidator`
- Produces: `medir.py` com `run(fixture: Path) -> FixtureResult`, campos `contract_ok`, `compiled`, `behavior_ok`, `untouched`; saida `N de 5`

- [ ] **Step 1: Criar as fixtures**

| Fixture | Entrada | O que prova |
|---|---|---|
| E1 | texto, heranca + regra de porcentagem, sem instrucao de `main`, nomes inventados | funciona sem decoreba e nao inventa classe de teste |
| E2 | texto em lista/tabela, sem a palavra `class` | entende enunciado escrito de outro jeito |
| E3 | texto, 3 classes, associacao + "nunca pode ser maior que" | respeita regra de negocio |
| E4 | PDF sintetico, mesma estrutura de E1 | entrada por PDF continua funcionando |
| E5 | `tests/fixtures/frota/` (desafio real + validador) | aprovacao no juiz real |

Cada `expected/*.json` guarda classes, campos, metodos e assinaturas esperadas, no formato de `uml/models.py`.

- [ ] **Step 2: Escrever o medidor**

`medir.py` aceita `--fixture E1` ou roda todas, e para cada uma responde as quatro perguntas do cabecalho. Para E5, o `behavior_ok` e o resultado de `tests/acceptance/validator.sh`, nao do arnes proprio.

- [ ] **Step 3: Rodar e registrar a linha de base**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python tests/qualidade/medir.py`
Expected: imprime `N de 5` e o motivo de cada falha. Copiar a saida para `tests/acceptance/qualidade.md` com data.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures tests/qualidade tests/acceptance/qualidade.md
git commit -m "test: add enunciado fidelity fixtures and baseline"
```

### Task 3: Um erro nao derruba o chat

**Files:**
- Modify: `src/java_assistant/cli.py`, `src/java_assistant/session.py`
- Test: `tests/unit/test_cli.py`, `tests/integration/test_session_flow.py`

**Interfaces:**
- Consumes: `SessionReply(text, exit_requested)`
- Produces: `run_cli` nunca propaga excecao; `AssistantSession.handle` converte falha em `SessionReply` com o motivo

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_unreadable_pdf_keeps_chat_alive(self):
    session = self.session_with_failing_pdf()
    session.handle("/pdf")
    reply = session.handle("1")
    self.assertIn("PDF", reply.text)
    self.assertFalse(reply.exit_requested)
    self.assertIn("Nenhum PDF", session.handle("/pdf").text or "")
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest tests.integration.test_session_flow -v`
Expected: FAIL — sobe `PdfExtractionError`.

- [ ] **Step 3: Implementar a fronteira de erro**

Em `handle()`, envolver o despacho em `try/except (PdfExtractionError, OSError, ValueError, RuntimeError)` devolvendo `SessionReply("Não consegui concluir: ...")`. Em `cli.py`, reduzir o `try` do `main()` ao startup, deixando `run_cli` fora — a mensagem atual ("Não foi possível iniciar") mente sobre a causa.

- [ ] **Step 4: Rodar e commitar**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests`
Expected: PASS
```bash
git commit -am "fix: keep chat alive when a request fails"
```

### Task 4: Resposta cortada nao vira erro de sintaxe

**Files:**
- Modify: `src/java_assistant/model/client.py`, `src/java_assistant/session.py`
- Test: `tests/unit/model/test_client.py`, `tests/integration/test_session_flow.py`

**Interfaces:**
- Consumes: `LocalHttpTransport(payload)` (dict -> dict)
- Produces: `ModelReply(content, truncated: bool)`; `ModelClient.complete(messages, *, max_tokens: int | None = None)`

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_transport_accepts_per_call_max_tokens(self):
    transport = LocalHttpTransport(1234, opener=self.opener)
    transport({"messages": [], "max_tokens": 1024})
    self.assertEqual(self.sent_body["max_tokens"], 1024)

def test_length_finish_reason_marks_reply_truncated(self):
    reply = self.client.complete([Message("user", "x")])
    self.assertTrue(reply.truncated)

def test_truncated_reply_retries_with_explicit_message(self):
    reply = self.session.handle("resolva")
    self.assertIn("cortada", reply.text)
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest tests.unit.model.test_client -v`
Expected: FAIL — `ModelReply` nao tem `truncated`.

- [ ] **Step 3: Implementar**

`LocalHttpTransport.__call__` ja faz `setdefault("max_tokens", 384)`; trocar por repasse do valor da chamada. `ModelClient.complete` le `choices[0].finish_reason` e marca `truncated` quando for `"length"`. `_generate_one_class` passa `max_tokens=1200` e, ao receber `truncated`, pede a classe em duas partes em vez de repetir o mesmo pedido.

- [ ] **Step 4: Rodar e commitar**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests`
Expected: PASS
```bash
git commit -am "fix: detect truncated model replies"
```

### Task 5: Arrancar o Frota de dentro do produto

**Files:**
- Modify: `src/java_assistant/session.py`
- Test: `tests/unit/test_no_exercise_hardcode.py` (novo), `tests/integration/test_session_flow.py`

**Interfaces:**
- Consumes: `_focused_requirements(name) -> str`, `_semantic_issues(requirements, source) -> tuple[str, ...]`
- Produces: `_required_generation_rules(requirements: str) -> tuple[str, ...]` generica: `aumento de N%` -> `base * (1 + N/100)`, `redu[c]ao de N%` -> `base * (1 - N/100)`, `metade` -> `* 0.5`, `um quarto` -> `* 0.75`, `nunca ... maior que` -> exigir validacao explicita

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_product_mentions_no_exercise_specific_names(self):
    forbidden = ("Frota", "Veiculo", "Motocicleta", "Hatch", "Pickup",
                 "autonomia", "cilindrada", "bagageiro", "cambiao")
    for path in Path("src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for word in forbidden:
            self.assertNotIn(word, text, f"{word} em {path}")

def test_percentage_rule_is_derived_not_remembered(self):
    rules = _required_generation_rules("O volume aumenta em 25%")
    self.assertIn("base * 1.25", "\n".join(rules))

def test_generic_class_with_autonomia_method_is_not_special_cased(self):
    issues = _semantic_issues("CLASSE: Conta\n+ autonomia(): Double", "return super.autonomia();")
    self.assertEqual(issues, ())
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest tests.unit.test_no_exercise_hardcode -v`
Expected: FAIL — encontrado `Frota` em `session.py`.

- [ ] **Step 3: Remover e substituir**

Apagar os blocos `if "aumenta em 100%"`, `if "aumenta em 50%"`, `if reduzid[ao] em um quarto`, `if "reduzida pela metade"`, o bloco `autonomia` de `_semantic_issues` e o correspondente em `_focused_requirements`. Implementar `_required_generation_rules` com expressao regular numerica unica. Trocar `main_class="Frota"` em `_ACTION_PROTOCOL` por `main_class="Main"`.

- [ ] **Step 4: Rodar e commitar**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests`
Expected: PASS
```bash
git commit -am "refactor: derive rules from the enunciado instead of hardcoding an exercise"
```

### Task 6: Entender enunciado escrito de outro jeito

**Files:**
- Modify: `src/java_assistant/uml/extract.py`, `src/java_assistant/uml/models.py`
- Test: `tests/unit/uml/test_variants.py` (novo), `tests/integration/test_pdf_uml.py`

**Interfaces:**
- Consumes: `PdfEvidence.text`
- Produces: `UmlExtractor().extract(evidence) -> JavaContract`, agora aceitando `CLASSE:`, `Classe X`, `class X`, `X:`; membros `- nome: Tipo`, `private Tipo nome;`, `+ nome(tipo): Tipo`, `+ Nome(tipo)`; e `JavaContract.warnings` preenchido quando nada foi reconhecido

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_reads_java_style_attribute_lines(self):
    contract = self.extract("CLASSE: Conta\nprivate double saldo;\npublic double getSaldo()")
    self.assertEqual(contract.classes[0].fields[0].visibility, "private")

def test_reads_markdown_list_members(self):
    contract = self.extract("## Conta\n- saldo: double\n- sacar(valor: double): boolean")
    self.assertEqual(len(contract.classes[0].methods), 1)

def test_empty_contract_carries_a_warning(self):
    contract = self.extract("texto sem diagrama nenhum")
    self.assertEqual(contract.classes, ())
    self.assertTrue(contract.warnings)
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest tests.unit.uml.test_variants -v`
Expected: FAIL

- [ ] **Step 3: Implementar as variantes e o aviso**

Cada variante e uma expressao regular adicional em `uml/extract.py`; manter `confidence` o mesmo padrao. `warnings` recebe `("Nenhuma classe reconhecida no enunciado.",)` quando `classes` fica vazio.

- [ ] **Step 4: Bloquear geracao com contrato vazio**

Em `session._chat`, se `self._contract` existe e `not self._contract.classes`, responder o `warnings` e pedir o diagrama em vez de chamar `_guided_solve`. Teste correspondente em `test_session_flow.py`.

- [ ] **Step 5: Rodar e commitar**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests`
Expected: PASS
```bash
git commit -am "feat: read common enunciado variants and warn on empty contracts"
```

### Task 7: `/contrato`

**Files:**
- Modify: `src/java_assistant/session.py`
- Test: `tests/integration/test_session_flow.py`

**Interfaces:**
- Consumes: `JavaContract` (`classes`, `relationships`, `warnings`)
- Produces: `_render_contract() -> str` com uma linha por classe, membros e heranca, e uma secao final de incertezas

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_contrato_lists_classes_members_and_inheritance(self):
    self.session.handle("/enunciado"); self.session.handle(ENUNCIADO_E1); self.session.handle("/fim")
    text = self.session.handle("/contrato").text
    self.assertIn("Conta", text)
    self.assertIn("saldo: double", text)
    self.assertIn("extends", text)
```

- [ ] **Step 2: Rodar, implementar, rodar**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest tests.integration.test_session_flow -v`
Expected: FAIL, depois de implementar `_render_contract` em `handle()`, PASS.

- [ ] **Step 3: Commit**

```bash
git commit -am "feat: add /contrato to review the parsed enunciado"
```

### Task 8: Juiz proprio (assinaturas e comportamento)

**Files:**
- Create: `src/java_assistant/java/judge.py`
- Modify: `src/java_assistant/java/toolchain.py`, `src/java_assistant/session.py`
- Test: `tests/unit/java/test_judge.py` (novo), `tests/integration/test_java_toolchain.py`

**Interfaces:**
- Consumes: `JavaToolchain.compile`, `JavaToolchain.run`, `JavaToolchain.inspect`, `JavaContract`
- Produces: `RuleCase(class_name, constructor_args, method, args, expected)`; `Judge.build_cases(contract, enunciado) -> list[RuleCase]`; `Judge.run(cases) -> JudgeReport(passed, failed, unverified)`; `JavaToolchain.run_class(class_name, timeout_s)` para executar o arnes compilado fora da entrega

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_arsenal_rejects_double_returned_as_primitive(self):
    report = self.judge_run("public double autonomia(){return 500.0;}", expected="Double")
    self.assertFalse(report.passed)
    self.assertIn("autonomia", report.failed[0])

def test_constructor_missing_inherited_parameters_is_rejected(self):
    report = self.judge_run(HATCH_SEM_HERDADOS)
    self.assertIn("Hatch", report.failed[0])

def test_super_effect_composes_with_subclass_effect(self):
    self.assertEqual(self.judge_expected("Pickup", cambio=True, carga="total"), 225.0)

def test_invariant_violation_must_throw(self):
    report = self.judge_run(PICKUP_SEM_VALIDACAO)
    self.assertIn("IllegalArgumentException", report.failed[0])

def test_rules_without_enough_information_are_reported_unverified(self):
    report = self.judge_run(SOLUCAO_SEM_REGRA_DECLARADA)
    self.assertTrue(report.unverified)
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest tests.unit.java.test_judge -v`
Expected: FAIL — `java_assistant.java.judge` nao existe.

- [ ] **Step 3: Implementar a conferencia de assinatura**

Reutilizar `ContractValidator` para estrutura e acrescentar a comparacao exata de tipo de retorno: `javap -p` imprime `java.lang.Double`; apos normalizar, comparar com `member.type_name` sem converter `Double` para `double`.

- [ ] **Step 4: Implementar o arnes de comportamento**

`Judge` escreve uma classe `AssistenteVerificacao` em diretorio temporario, fora do projeto, com um `main` que instancia cada `RuleCase`, chama o metodo e compara com `expected`. Casos sem regra derivavel vao para `unverified`, nunca para `passed`. Os casos sao derivados de `_required_generation_rules` (Task 5), nao de nomes de exercicio.

- [ ] **Step 5: Ligar ao fluxo e limitar tentativas**

Em `_guided_solve`, apos compilar: rodar o juiz; se houver falha e restarem tentativas (limite 2), regenerar apenas a classe citada com o diagnostico; se ainda falhar, devolver o relatorio com `failed` e `unverified` explicitos. `evidence.locally_tested` passa a receber o resultado do juiz, nao a execucao de `main`.

- [ ] **Step 6: Rodar e commitar**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests`
Expected: PASS
```bash
git commit -am "feat: judge generated classes by instantiating them"
```

### Task 9: `/alteracoes` e ajuste focado

**Files:**
- Modify: `src/java_assistant/session.py`, `src/java_assistant/workspace/history.py`
- Test: `tests/unit/workspace/test_history.py`, `tests/integration/test_session_flow.py`

**Interfaces:**
- Consumes: `History` (lista de `Change` com `before_content`, `after_hash`)
- Produces: `_render_changes() -> str` com nome do arquivo e um diff unificado; garantia de que um pedido de correcao em uma classe nao regenera as demais

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_alteracoes_shows_unified_diff_of_last_changes(self):
    text = self.session.handle("/alteracoes").text
    self.assertIn("--- Conta.java", text)
    self.assertIn("+++ Conta.java", text)

def test_correction_touches_only_the_requested_class(self):
    before = self.hashes()
    self.session.handle("corrija somente Conta")
    self.assertEqual({k for k, v in self.hashes().items() if v != before[k]}, {"Conta.java"})
```

- [ ] **Step 2: Rodar, implementar, rodar, commitar**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest tests.integration.test_session_flow -v`
Expected: FAIL, depois PASS.
```bash
git commit -am "feat: show diffs and keep corrections scoped"
```

### Task 10: Limpar diretorios temporarios

**Files:**
- Modify: `src/java_assistant/java/toolchain.py`
- Test: `tests/integration/test_java_toolchain.py`

**Interfaces:**
- Consumes: `tempfile.mkdtemp(prefix="java-assistente-classes-")`
- Produces: `JavaToolchain.close()` que remove o diretorio de classes; chamada em `AssistantSession.close()`

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_compile_does_not_leave_temporary_directories(self):
    before = set(Path(tempfile.gettempdir()).glob("java-assistente-classes-*"))
    self.toolchain.compile([Path("Calculadora.java")])
    self.toolchain.close()
    after = set(Path(tempfile.gettempdir()).glob("java-assistente-classes-*"))
    self.assertEqual(after - before, set())
```

- [ ] **Step 2: Rodar, implementar `close()` com `shutil.rmtree(..., ignore_errors=True)`, chamar em `session.close()`, rodar e commitar**

```bash
git commit -am "fix: remove compiled classes temporary directory"
```

### Task 11: Memoria portatil entre sessoes

Executar o plano inteiro de `docs/superpowers/plans/2026-10-22-memoria-portatil-entre-sessoes.md` (Tasks 1 a 8), com estes ajustes de integracao ja decididos aqui:

- [ ] **Step 1: Substituir a identidade por caminho absoluto** (`memory/store.py:project_identifier`) por uma identidade gravada em `.assistente/manifest.json`, para que mover a pasta nao apague a memoria.
- [ ] **Step 2: Persistir o contrato extraido de enunciado em texto**, com `pdf_hash = "texto-" + sha256(conteudo)`, ja que agora a entrada pode nao ser PDF.
- [ ] **Step 3: Ao retomar uma sessao, reapresentar o `/contrato`** e nao repetir classes que ja passaram pelo juiz.
- [ ] **Step 4: Rodar a suite completa e a aceitacao antes de commitar.**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests`
Expected: PASS

### Task 12: Medir de novo e registrar

**Files:**
- Modify: `tests/acceptance/qualidade.md`, `tests/acceptance/checklist.md`
- Create: `tests/acceptance/validator.sh`

**Interfaces:**
- Consumes: `tests/qualidade/medir.py`, `tests/fixtures/frota/Frota.class`
- Produces: `validator.sh <pasta-da-solucao>` — compila, copia os `.class` para um diretorio temporario e roda `java -cp "<temp>:<fixtures>" Frota --console`

- [ ] **Step 1: Escrever o script do validador real**

```sh
#!/bin/sh
set -eu
[ "$#" -eq 1 ] || { echo "uso: $0 pasta-da-solucao" >&2; exit 2; }
SOL=$(cd "$1" && pwd); FIX=$(cd "$(dirname "$0")/../fixtures/frota" && pwd)
OUT=$(mktemp -d); trap 'rm -rf "$OUT"' EXIT
javac --release 8 -d "$OUT" "$SOL"/*.java
java -cp "$OUT:$FIX" Frota --console
```

- [ ] **Step 2: Rodar o medidor completo**

Run: `$env:PYTHONPATH=(Resolve-Path src).Path; python tests/qualidade/medir.py`
Expected: `N de 5`. Registrar a comparacao com a linha de base.

- [ ] **Step 3: Registrar o validador real**

Run (Linux/WSL): `bash tests/acceptance/validator.sh /caminho/da/solucao`
Expected: todas as linhas da bateria conferem, incluindo `Pickup 225,00` e a excecao de carga invalida.

- [ ] **Step 4: Atualizar a checklist e commitar**

```bash
git add tests/acceptance
git commit -m "test: measure fidelity against fixtures and the real validator"
```

---

## Fora de escopo (decidido com o usuario)

- Empacotamento dentro de 1,5 GB, medicao de RAM e USB 2.0: o bundle atual ja cumpre o limite rigido de 2 GB; a medicao depende do hardware real.
- Visao computacional para diagrama desenhado: `pdftoppm` + coordenadas do OCR (`pdftotext -bbox`) cobrem o caso, sem dependencia nova. Reavaliar so se um enunciado real escapar.
- Qualquer garantia sobre os testes secretos dos jurados.
- Comandos da spec sem tarefa propria: `/implementar`, `/compilar`, `/testar`, `/revisar`, `/criterios`, `/memoria`, `/diagnostico`. A linguagem natural ja dispara os dois primeiros, o juiz (Task 8) cobre o que `/testar` faria, `/alteracoes` (Task 9) cobre a conferencia das mudancas, e os quatro restantes so viram tarefa se o usuario pedir.
- Leitura visual do diagrama em PDF escaneado: so entra se um enunciado real escapar do extrator de coordenadas.
