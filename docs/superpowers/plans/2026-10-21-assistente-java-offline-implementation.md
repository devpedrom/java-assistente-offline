# Assistente Java POO Offline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar um assistente de terminal instalavel offline no Linux Mint, especializado em Java POO, que leia PDFs com UML sob demanda, crie e valide codigo na pasta atual e preserve memoria para microajustes.

**Architecture:** Um aplicativo Python empacotado controla um `llama-server` local com modelo GGUF e expoe ao modelo somente acoes estruturadas e validadas. Adaptadores separados cuidam de workspace, PDF/UML, Java, memoria e relatorios; o pacote Linux inclui todos os binarios e um instalador offline de um comando.

**Tech Stack:** Python 3.11, pytest, llama.cpp, Qwen2.5-Coder-1.5B-Instruct Q4_K_M, SQLite, Poppler, Tesseract, OpenCV, OpenJDK 17 compilando com `--release 8`, PyInstaller e shell POSIX.

**Spec:** `docs/superpowers/specs/2026-10-21-assistente-java-offline-design.md`

## Global Constraints

- Alvo: Linux Mint x86-64, CPU fraca, 4 a 6 GB de RAM, sem GPU dedicada.
- Instalacao e uso 100% offline, sem `sudo` e sem gerenciador de pacotes no computador-alvo.
- Um unico `./instalar.sh` copia, configura, verifica e inicia o chat; usos posteriores executam `java-assistente`.
- O bundle deve ter no maximo 2 GB, alvo de 1,5 GB, e mostrar o primeiro prompt em ate 5 minutos usando USB 2.0 funcional.
- Instalacao nao pode compilar, baixar ou converter componentes; deve copiar poucos artefatos previamente preparados.
- A pasta de trabalho atual na inicializacao e a raiz imutavel do projeto e o limite de escrita.
- `/pdf` lista somente PDFs da raiz atual e exige escolha numerica.
- Codigo gerado deve ser compativel com Java 8 por padrao.
- `CRITERIOS_GERAIS.md` e carregado integralmente antes de gerar, revisar ou corrigir codigo.
- O modelo nunca executa shell diretamente; toda acao passa por esquema, allowlist, timeout e validacao de caminho.
- Nenhum dado, telemetria ou requisicao pode sair da maquina; HTTP local do `llama-server` deve usar apenas `127.0.0.1`.
- Nenhuma regra ou classe do exercicio Frota pode ser codificada no produto.

## Review Focus

- Caminho com espacos e acentos: `/pdf`, escrita e compilacao devem funcionar sem truncamento ou mudanca de pasta.
- PDF sem camada de texto: renderizacao e OCR devem produzir contrato ou incerteza explicita, nunca sucesso vazio.
- Acao do modelo tentando `../` ou caminho absoluto: deve ser rejeitada antes de tocar o sistema de arquivos.
- Processo Java em loop infinito: deve ser encerrado no timeout sem encerrar o assistente.
- Reinstalacao: deve atualizar binarios sem sobrescrever `CRITERIOS_GERAIS.md`, memoria ou projetos.

---

## File Structure

```text
pyproject.toml
src/java_assistant/
  cli.py                 # loop do terminal e comandos do usuario
  session.py             # maquina de estados do fluxo hibrido
  config.py              # caminhos XDG e limites de recursos
  model/runtime.py       # ciclo de vida do llama-server
  model/client.py        # chat local e montagem de contexto
  model/actions.py       # esquema e validacao de acoes
  workspace/files.py     # leitura/escrita confinada e atomica
  workspace/history.py   # patches e desfazer
  pdf/discovery.py       # implementacao do comando /pdf
  pdf/extract.py         # texto, renderizacao e OCR
  uml/models.py          # contrato Java estruturado
  uml/extract.py         # caixas, membros e relacionamentos
  java/toolchain.py      # javac/java portateis e timeouts
  java/validator.py      # estrutura, assinaturas e compilacao
  java/tester.py         # testes locais separados da entrega
  memory/store.py        # memoria SQLite por hash de PDF/projeto
  review/report.py       # relatorio de evidencias
tests/
  fixtures/
  unit/
  integration/
packaging/linux/
  instalar.sh
  desinstalar.sh
  java-assistente
  build-bundle.sh
  manifest.sha256
instructions/CRITERIOS_GERAIS.md
```

### Task 1: Base executavel e CLI na pasta atual

**Files:**
- Create: `pyproject.toml`
- Create: `src/java_assistant/cli.py`
- Create: `src/java_assistant/config.py`
- Create: `tests/unit/test_cli.py`
- Create: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `AppConfig.load(cwd: Path) -> AppConfig`, `run_cli(config: AppConfig, input_fn: Callable) -> int`.

- [ ] **Step 1: Escrever testes falhos** para provar que `cwd.resolve()` vira `project_root`, que o prompt aceita texto comum e que `/sair` encerra com codigo zero.
- [ ] **Step 2: Executar** `pytest tests/unit/test_cli.py tests/unit/test_config.py -v`; esperado: falha de importacao.
- [ ] **Step 3: Implementar a base minima** com `project_root` imutavel, diretorios XDG configuraveis e registro de comandos sem logica de dominio.
- [ ] **Step 4: Executar os testes**; esperado: todos passam.
- [ ] **Step 5: Inicializar Git e registrar** `git init && git add pyproject.toml src tests && git commit -m "feat: add offline assistant CLI foundation"`.

### Task 2: Runtime local do modelo e protocolo de acoes

**Files:**
- Create: `src/java_assistant/model/runtime.py`
- Create: `src/java_assistant/model/client.py`
- Create: `src/java_assistant/model/actions.py`
- Create: `tests/unit/model/test_runtime.py`
- Create: `tests/unit/model/test_actions.py`

**Interfaces:**
- Consumes: `AppConfig`.
- Produces: `LlamaRuntime.start() -> None`, `LlamaRuntime.stop() -> None`, `ModelClient.complete(messages: list[Message]) -> ModelReply`, `parse_action(text: str) -> Action`.

- [ ] **Step 1: Escrever testes falhos** para inicializacao em `127.0.0.1`, encerramento limpo, timeout, JSON invalido e rejeicao de nome de ferramenta fora da allowlist.
- [ ] **Step 2: Executar** `pytest tests/unit/model -v`; esperado: falhas por modulos ausentes.
- [ ] **Step 3: Implementar o processo filho** com porta local dinamica, limites conservadores e verificacao de prontidao sem acesso externo.
- [ ] **Step 4: Implementar o parser de acoes** com tipos fechados para leitura, escrita, patch, compilacao, teste, PDF e memoria.
- [ ] **Step 5: Executar os testes**; esperado: todos passam.
- [ ] **Step 6: Registrar** `git commit -am "feat: add local model runtime and action protocol"`.

### Task 3: Workspace confinado, alteracoes atomicas e desfazer

**Files:**
- Create: `src/java_assistant/workspace/files.py`
- Create: `src/java_assistant/workspace/history.py`
- Create: `tests/unit/workspace/test_files.py`
- Create: `tests/unit/workspace/test_history.py`

**Interfaces:**
- Consumes: `AppConfig.project_root` e `Action`.
- Produces: `Workspace.read(relative: Path) -> str`, `Workspace.write(relative: Path, content: str) -> Change`, `Workspace.apply_patch(...) -> Change`, `History.undo_last() -> UndoResult`.

- [ ] **Step 1: Escrever testes falhos** para caminho normal, espacos/acentos, `../`, caminho absoluto, symlink que escapa da raiz, gravacao atomica e desfazer que preserva edicao posterior do usuario.
- [ ] **Step 2: Executar** `pytest tests/unit/workspace -v`; esperado: falha.
- [ ] **Step 3: Implementar resolucao canonica e bloqueios** antes de qualquer abertura de arquivo.
- [ ] **Step 4: Implementar historico por patches** com hash anterior/posterior e recusa de desfazer quando o arquivo divergiu.
- [ ] **Step 5: Executar os testes**; esperado: todos passam.
- [ ] **Step 6: Registrar** `git commit -am "feat: confine workspace changes and support undo"`.

### Task 4: `/pdf`, extracao e contrato UML

**Files:**
- Create: `src/java_assistant/pdf/discovery.py`
- Create: `src/java_assistant/pdf/extract.py`
- Create: `src/java_assistant/uml/models.py`
- Create: `src/java_assistant/uml/extract.py`
- Create: `tests/fixtures/uml-simples.pdf`
- Create: `tests/fixtures/uml-imagem.pdf`
- Create: `tests/unit/pdf/test_discovery.py`
- Create: `tests/integration/test_pdf_uml.py`

**Interfaces:**
- Produces: `discover_pdfs(root: Path) -> list[Path]`, `PdfExtractor.extract(path: Path) -> PdfEvidence`, `UmlExtractor.extract(evidence: PdfEvidence) -> JavaContract`.

- [ ] **Step 1: Criar fixtures sinteticas** com duas classes, heranca, atributos, construtor e metodo; uma com texto vetorial e outra somente imagem.
- [ ] **Step 2: Escrever testes falhos** para lista alfabetica numerada apenas na raiz, caminhos com acentos, PDF sem texto, heranca extraida e campo `confidence` para relacoes incertas.
- [ ] **Step 3: Executar** `pytest tests/unit/pdf tests/integration/test_pdf_uml.py -v`; esperado: falha.
- [ ] **Step 4: Implementar descoberta e extracao** usando Poppler, OCR TSV e arquivos temporarios fora da entrega.
- [ ] **Step 5: Implementar contrato UML** com classes, membros, visibilidade, tipos e relacionamentos; resultados ambiguos devem gerar alternativas, nao valores inventados.
- [ ] **Step 6: Executar os testes**; esperado: ambos os PDFs produzem contrato equivalente ou incerteza explicita.
- [ ] **Step 7: Registrar** `git commit -am "feat: extract Java contracts from PDF UML"`.

### Task 5: Ferramentas Java, validacao e testes locais

**Files:**
- Create: `src/java_assistant/java/toolchain.py`
- Create: `src/java_assistant/java/validator.py`
- Create: `src/java_assistant/java/tester.py`
- Create: `tests/fixtures/java/simple/`
- Create: `tests/integration/test_java_toolchain.py`
- Create: `tests/integration/test_java_timeout.py`

**Interfaces:**
- Consumes: `JavaContract`, `Workspace` e caminhos do JDK.
- Produces: `JavaToolchain.compile(sources: list[Path]) -> CompileResult`, `JavaToolchain.run(main_class: str, timeout_s: int) -> RunResult`, `ContractValidator.validate(contract, root) -> ValidationReport`.

- [ ] **Step 1: Escrever testes falhos** para compilacao `--release 8`, erro com arquivo/linha, reflexao de assinaturas, formula simples e programa em loop infinito.
- [ ] **Step 2: Executar** `pytest tests/integration/test_java_toolchain.py tests/integration/test_java_timeout.py -v`; esperado: falha.
- [ ] **Step 3: Implementar invocacao do JDK empacotado** sem shell, com argumentos separados, diretorio temporario de classes e timeout por grupo de processo.
- [ ] **Step 4: Implementar validacao estrutural e executor de testes** sem colocar fontes de teste na entrega final.
- [ ] **Step 5: Executar os testes**; esperado: compilacao valida passa, diagnostico invalido e timeout sao capturados.
- [ ] **Step 6: Registrar** `git commit -am "feat: compile and validate Java 8 solutions"`.

### Task 6: Criterios gerais e memoria persistente

**Files:**
- Create: `src/java_assistant/memory/store.py`
- Create: `instructions/CRITERIOS_GERAIS.md`
- Create: `tests/unit/memory/test_store.py`
- Create: `tests/unit/test_criteria.py`

**Interfaces:**
- Produces: `ProjectStore.open(pdf_hash: str, project_id: str) -> ProjectStore`, `load_criteria(config: AppConfig) -> str`, `build_context(...) -> list[Message]`.

- [ ] **Step 1: Escrever testes falhos** para persistencia apos reinicio, isolamento entre PDFs, resumo compacto, carga integral dos criterios e reinstalacao que nao sobrescreve o arquivo editado.
- [ ] **Step 2: Executar** `pytest tests/unit/memory tests/unit/test_criteria.py -v`; esperado: falha.
- [ ] **Step 3: Implementar SQLite** com migracoes versionadas, hash SHA-256 do PDF, decisoes, contrato, compilacao, testes e alteracoes.
- [ ] **Step 4: Implementar montagem de contexto** contendo criterios completos, contrato, resumo e somente arquivos relevantes ao pedido atual.
- [ ] **Step 5: Executar os testes**; esperado: todos passam.
- [ ] **Step 6: Registrar** `git commit -am "feat: persist project memory and judge criteria"`.

### Task 7: Orquestracao hibrida e relatorio honesto

**Files:**
- Create: `src/java_assistant/session.py`
- Create: `src/java_assistant/review/report.py`
- Modify: `src/java_assistant/cli.py`
- Create: `tests/integration/test_session_flow.py`
- Create: `tests/integration/test_ambiguous_uml.py`

**Interfaces:**
- Consumes: todas as interfaces das Tasks 2 a 6.
- Produces: `AssistantSession.handle(text: str) -> SessionReply`, `EvidenceReport.render() -> str`.

- [ ] **Step 1: Escrever teste falho de ponta a ponta simulado**: iniciar na pasta, `/pdf`, escolher por numero, extrair contrato, pedir "Resolva", escrever fontes, compilar, testar e manter chat aberto.
- [ ] **Step 2: Escrever teste falho de ambiguidade** que impede geracao ate o usuario escolher uma interpretacao.
- [ ] **Step 3: Executar** `pytest tests/integration/test_session_flow.py tests/integration/test_ambiguous_uml.py -v`; esperado: falha.
- [ ] **Step 4: Implementar a maquina de estados** com no maximo tres tentativas automaticas por falha e microajuste limitado aos arquivos relacionados.
- [ ] **Step 5: Implementar relatorio** com as cinco secoes exatas da especificacao e sem alegar aprovacao oficial.
- [ ] **Step 6: Executar** `pytest -q`; esperado: suite completa passa.
- [ ] **Step 7: Registrar** `git commit -am "feat: complete hybrid Java assistant workflow"`.

### Task 8: Pacote Linux e instalador de um comando

**Files:**
- Create: `packaging/linux/build-bundle.sh`
- Create: `packaging/linux/instalar.sh`
- Create: `packaging/linux/desinstalar.sh`
- Create: `packaging/linux/java-assistente`
- Create: `tests/packaging/test_installer.py`
- Create: `docs/USO-RAPIDO.md`

**Interfaces:**
- Consumes: executavel PyInstaller, modelo, llama.cpp, JDK, Poppler, Tesseract e manifestos.
- Produces: `dist/java-assistente-linux-x86_64/` pronto para copiar ao pendrive.

- [ ] **Step 1: Escrever testes falhos do instalador** em raizes XDG temporarias: uma execucao instala e inicia; a segunda atualiza binarios e preserva criterios/memoria; nenhuma usa `sudo` ou rede; o manifesto contem no maximo quatro artefatos principais para copia.
- [ ] **Step 2: Executar** `pytest tests/packaging/test_installer.py -v`; esperado: falha.
- [ ] **Step 3: Implementar `build-bundle.sh`** para gerar um runtime compactado, manter o GGUF ja quantizado como arquivo separado, exigir artefatos previamente baixados, verificar SHA-256 e rejeitar bundle acima de 2 GB.
- [ ] **Step 4: Implementar `instalar.sh` idempotente** com um unico comando visivel, copia atomica, launcher no PATH do usuario e inicio automatico do chat.
- [ ] **Step 5: Implementar desinstalacao segura** que preserve criterios e memoria por padrao e nunca remova projetos.
- [ ] **Step 6: Executar testes do instalador e `pytest -q`**; esperado: todos passam.
- [ ] **Step 7: Registrar** `git commit -am "feat: package one-command offline Linux installer"`.

### Task 9: Aceitacao no Linux Mint compativel

**Files:**
- Create: `tests/acceptance/run-offline.sh`
- Create: `tests/acceptance/checklist.md`
- Modify: `docs/USO-RAPIDO.md`

**Interfaces:**
- Consumes: bundle final da Task 8.
- Produces: registro reproduzivel de aceitacao e hashes do pacote aprovado.

- [ ] **Step 1: Instalar o bundle em ambiente Linux x86-64 limpo** com rede desativada e diretorios de usuario temporarios.
- [ ] **Step 2: Verificar a instalacao de um comando** e confirmar que o chat abre depois que a origem do pendrive simulado fica indisponivel.
- [ ] **Step 3: Executar o fluxo real** com PDF UML sintetico, pasta com espacos/acentos, geracao Java, compilacao, teste, microajuste, reinicio e `/desfazer`.
- [ ] **Step 4: Medir o pico de memoria** no perfil conservador; esperado: cabe em 4 GB sem swap excessiva ou encerramento por falta de memoria.
- [ ] **Step 5: Medir instalacao e primeira inicializacao** a partir de midia limitada a velocidade de USB 2.0; esperado: primeiro prompt em no maximo 5 minutos e bundle com alvo de ate 1,5 GB.
- [ ] **Step 6: Auditar rede e confinamento**; esperado: somente loopback do llama-server e nenhuma escrita fora da raiz do projeto/configuracao/estado.
- [ ] **Step 7: Registrar hashes e resultados** em `tests/acceptance/checklist.md`; qualquer item nao executado permanece explicitamente pendente.
- [ ] **Step 8: Registrar** `git commit -am "test: validate offline Linux acceptance flow"`.

