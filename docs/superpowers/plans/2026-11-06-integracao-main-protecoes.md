# Proteções compartilhadas na main — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar o primeiro incremento de proteções do commit ef57eb8 à main, preservando núcleo, perfis, adaptadores e dados existentes.

**Architecture:** Alterar uma vez os limites compartilhados de escrita/cleanup e adaptar seus chamadores. Não copiar session.py/solver.py da origem nem criar esquema concorrente de contrato ou memória.

**Tech Stack:** Python 3.10+, biblioteca padrão, unittest, JDK já disponível; nenhuma dependência nova.

**Spec:** `docs/superpowers/specs/2026-11-06-integracao-seletiva-main-design.md` — somente entrega A; B/C ficam fora deste plano.

## Global Constraints

- Base main5802591 em integracao/ajustes-main, worktree isolado; não alterar checkout original.
- Offline, Java 8, raiz imutável, timeouts e ausência de shell para o modelo.
- Não ler/converter/reescrever `.assistente`, perfis do usuário ou memória SQLite antiga.
- Preservar Specification/Unit/Member, solver, adaptadores e todos os testes da main.
- Sem novas dependências, downloads, modelos, binários ou materiais privados em commits.
- Publicação sem force; merge somente se a main ainda for ancestral e os gates passarem.

## Review Focus

- Edição que muda somente LF/CRLF precisa bloquear undo e patches desatualizados — Task1.
- Arquivo criado por outro editor durante inferência não pode ser sobrescrito — Task1.
- Conflito imediatamente antes do replace não deixa temporário nem registro falso — Task1.
- Cleanup só remove diretórios temporários próprios, nunca classpath/projeto — Task2.
- Falha ao fechar sessão/SQLite não deixa runtime vivo nem exige close em adaptador de teste — Task2.

## Arquivos

- `workspace/files.py`: leitura e hashes exatos; guarda de conteúdo na escrita atômica.
- `workspace/history.py`: registro de gravação bem-sucedida e undo com guarda.
- `core/solver.py`, `session.py`: transportar o conteúdo esperado sem perder protocolo/perfil.
- `java/toolchain.py`, `cli.py`: liberação de recursos próprios, mesmo na falha.
- Testes existentes de workspace, solver, sessão, CLI e toolchain: regressões pequenas.
- `docs/ESTADO-DO-PROJETO.md`: inventário/evidências deste incremento, sem anunciar B/C.

### Task 1: Preservar bytes e impedir gravação sobre conteúdo inesperado

**Interfaces:** `Workspace.write(relative, content, *, expected=<sentinela>) -> Change`: sentinela mantém comportamento incondicional; str exige correspondência exata; None exige arquivo ausente. `History.write(relative, content, *, expected=<sentinela>) -> Change` registra só depois da escrita. `record` continua disponível para chamadores existentes.

- [ ] Criar testes que exijam read/undo byte-exatos com emoji e CRLF; alteração apenas de newline muda o hash e impede undo. Asserções sobre read_bytes, não read_text normalizado.
- [ ] Criar testes de escrita com conteúdo esperado errado, arquivo criado durante geração e edição durante fsync/preparação do temporário: PatchMismatchError, edição preservada, nenhum .tmp/novo histórico.
- [ ] Criar regressão no solver com modelo que edita/cria o alvo durante complete(): fonte externo preservado e geração interrompida claramente; não consumir tentativas extras para sobrescrever.
- [ ] Executar `python -m unittest tests.unit.workspace.test_files tests.unit.workspace.test_history tests.integration.test_solver -v` com PYTHONPATH=src; confirmar RED nos casos novos.
- [ ] Fazer digest e reads usarem UTF-8 sem normalização. Validar expected antes de preparar e novamente antes de substituir. Não enfraquecer `_resolve`, atomicidade ou fsync.
- [ ] Fazer History.write encaminhar expected e registrar apenas sucesso; undo restaura com expected atual para recusar edição concorrente. Manter métodos existentes sem persistência nova.
- [ ] Capturar estado do alvo antes da primeira chamada ao modelo no solver; escrever com History.write(expected=...). Propagar conflito como parada, não como nova tentativa de geração. Ações apply_patch continuam exigindo o texto esperado. Demais escritas usam o mesmo histórico sem alterar schemas de ações.
- [ ] Reexecutar os módulos anteriores e `tests.integration.test_session_flow`; confirmar PASS, inclusive caminhos do adaptador stub e melhor candidato restaurado.
- [ ] Registrar resultado e fazer commit específico deste incremento, sem incluir arquivos alheios.

### Task 2: Liberar classes temporárias e runtime com falhas de encerramento

**Interfaces:** `JavaToolchain.close() -> None`, idempotente e limitado a `_classes_dir`; chamar antes de nova compilação e ao fechar sessão. Toolchains simulados/externos sem close continuam suportados por cleanup opcional.

- [ ] Criar teste real do toolchain: compilar duas vezes elimina o primeiro diretório; close elimina o último e segunda chamada é segura. Caminhos extras de classpath/projeto ficam intactos.
- [ ] Criar testes: close da sessão fecha toolchain mesmo se store.close falhar; close inexistente no stub não causa erro; CLI chama runtime.stop mesmo se session.close falhar. Não mascarar a exceção original.
- [ ] Executar módulos dirigidos e observar RED antes da mudança.
- [ ] Acrescentar close ao JavaToolchain e usá-lo antes da nova pasta de compilação. Encadear limpeza da sessão/CLI com try/finally, preservando limites do perfil e mensagens existentes.
- [ ] Executar `python -m unittest tests.integration.test_java_toolchain tests.unit.test_cli tests.integration.test_session_flow -v`; confirmar PASS e nenhuma mudança de runtime/perfil/protocolo.
- [ ] Registrar resultado e fazer commit específico após evidência verde.

### Task 3: Verificar e publicar o primeiro incremento sem substituir a main

**Interfaces:** árvore descendente de main5802591 com somente A; B/C continuam adiados.

- [ ] Executar `PYTHONPATH=src python3 -m unittest discover -s tests -v` no WSL, com Java e ferramentas já preparadas no PATH. Registrar aprovados/falhas/erros/pulos e comparar com baseline Windows:227 executados,224 aprovados,3pulados,120.339s.
- [ ] Executar `git diff --check`; revisar diff e inventário contra a entrega A. Não anunciar build/modelo real/Mint que não foram executados; se packaging mudar, parar para executar seus gates adicionais.
- [ ] Pedir uma revisão independente do conjunto, corrigir achados importantes com RED→GREEN e suíte completa; não repetir revisões por tarefa.
- [ ] Atualizar docs com melhorias portadas, já existentes e adiadas; registrar limitações da origem14/17 sem atribuir esse resultado ao código integrado.
- [ ] Conferir remoto atualizado. Publicar integracao/ajustes-main, abrir PR com evidências e assistência de IA declarada. Se testes passarem e main não avançar, integrar por fast-forward/merge normal conforme autorização do usuário; nunca force.
- [ ] Verificar hash final remoto e estado do checkout original, sem tocar suas edições; informar links, resultado e próximos incrementos B/C.

## Handoff

Execução nativa recomendada: duas tarefas de código ligadas pela mesma escrita/histórico e uma verificação/publicação. O worktree e a baseline já existem. O desenho foi ajustado para preservar memórias e adiar conversão, conforme “prossiga”; revisão deste plano precede alterações de produto.
