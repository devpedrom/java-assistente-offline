# Correção por Método Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir corpos de métodos existentes sem reescrever atributos, construtores ou assinaturas.

**Architecture:** Um auxiliar Java confiável usa a AST do JDK existente para fornecer posições e identidades dos métodos. Python monta e valida cada candidato em temporário, confere conflitos e grava pelo histórico. O fluxo de primeira geração permanece inalterado.

**Tech Stack:** Python 3.10+, biblioteca padrão, JDK empacotado, unittest; sem dependências novas.

**Spec:** `docs/superpowers/specs/2026-11-06-correcao-por-metodo-design.md` (aprovada pelo usuário).

## Global Constraints

- Offline, mesmo modelo e mesmos binários; Java gerado compatível com Java 8.
- Raiz de escrita imutável; nenhuma ação de shell disponível ao modelo.
- Fontes reais só mudam após validação e sem perder edições externas.
- Sem nomes ou fórmulas de exercício no produto; sem commits/instalações implícitos.
- Preservar mudanças anteriores da branch, inclusive o plano de fidelidade ainda não concluído.

## Review Focus

- Offsets UTF-16 do compilador com caracteres não BMP antes do método: converter corretamente, Task 1.
- Sobrecargas e métodos de classes internas: identificar apenas a classe/método exatos, Task 1.
- Resposta que fecha o corpo e injeta outro membro: rejeitar pelo intervalo AST, Task 2.
- Fonte alterado durante validação: não sobrescrever a edição, Task 2.
- Auxiliar Java incluído no pacote e nenhuma classe de análise na entrega: Tasks 1/3.

## Arquivos

- `src/java_assistant/java/MethodBodies.java`: leitura sintática, sem executar o fonte inspecionado.
- `src/java_assistant/java/methods.py`: posições AST, extração de corpo e validação temporária.
- `src/java_assistant/session.py`: contexto de um método e integração de correções.
- `src/java_assistant/workspace/history.py`: gravação condicionada ao conteúdo esperado.
- `pyproject.toml`: incluir o auxiliar Java como dado de pacote.
- `tests/unit/java/test_methods.py`, `tests/integration/test_session_flow.py`, `tests/unit/workspace/test_history.py`: regressões.

### Task 1: Localizar métodos sem interpretar Java por regex

**Interfaces:** `MethodBody(name, parameter_types, start, end, signature)`; `locate_methods(toolchain, relative: Path, owner: str) -> tuple[MethodBody, ...]`.

- [x] Escrever testes com duas sobrecargas, construtor, método interno, strings/comentários com chaves e emoji anterior ao método. As fatias `source[start:end]` devem ser corpos completos; construtor e método interno não entram.
- [x] Executar `PYTHONPATH=src python -m unittest tests.unit.java.test_methods -v`; esperar falha por interfaces ausentes.
- [x] Implementar auxiliar com `JavacTask.parse`, `Trees.getSourcePositions`, `-proc:none`, timeouts e UTF-8; converter posições UTF-16. Validar caminhos pelo toolchain; remover temporários.
- [x] Incluir `*.java` em package-data; executar os testes e confirmar PASS.

### Task 2: Validar e gravar uma alteração exclusiva de corpo

**Interfaces:** `extract_body(text: str) -> str`; `validate_method(workspace, toolchain, contract, relative, method, body, expected_source) -> str`; `History.write(relative, content, *, expected=None)`.

- [x] Escrever testes: candidato válido muda somente o corpo; membro injetado e Java inválido são recusados; edição externa é preservada; nenhum `.class` aparece no projeto.
- [x] Executar o módulo de métodos e o de histórico; confirmar RED.
- [x] Montar candidato em cópia temporária validada dos fontes; verificar intervalo AST exato e contrato por `ContractValidator`. Rejeitar alterações externas e usar gravação com conteúdo esperado.
- [x] Executar `python -m unittest tests.unit.java.test_methods tests.unit.workspace.test_history -v`; esperar PASS.

### Task 3: Integrar o modelo e executar o desafio

**Interfaces:** `_correct_methods(class_name, request, diagnostic='') -> str | None`, usando as interfaces anteriores e mantendo os fluxos existentes de geração/compilação/relatório.

- [x] Escrever integração com modelo roteirizado retornando corpos: classe corrigida, atributos/construtor/outra classe idênticos; pedido explícito de método não altera outro; resposta inválida não altera o fonte.
- [x] Executar integração e confirmar RED.
- [x] Para classe existente em correção, pedir um corpo por chamada (`max_tokens=500`), no máximo duas tentativas por método. Fornecer assinatura, regras, corpo, campos/dependências e diagnóstico. Preservar a geração inicial. Em sobrecarga ambígua explicitamente solicitada, pedir identificação em vez de adivinhar.
- [x] Executar módulos dirigidos e suíte completa; esperar PASS e registrar skips/erros ambientais separadamente.
- [ ] Retomar somente `Hatch` no exercício persistido, sem editar Java à mão; executar bateria real e exigir as 17 aprovações pelo verificador independente.
- [x] Executar revisão independente uma vez; corrigir achados importantes com RED→GREEN, sem repetir tentativas cegas do modelo.
- [x] Atualizar pacote, executar aceitação WSL e registrar resultados/limites. O gate Mint e testes secretos continuam não comprovados.

## Execução e commits

Execução inline já autorizada pelo usuário ao aprovar a implementação. Commits não serão feitos sem permissão separada. Decisões e evidências ficam no ledger deste plano.

## Bloqueio de aceitação — 2026-11-06

O fluxo por método foi implementado e o protocolo funcionou com o modelo real,
mas os corpos retornados reproduziram os erros anteriores. A bateria fornecida
continua em **14/17**, sem correção manual dos fontes. Portanto o plano não está
inteiramente concluído: aprovação real permanece bloqueada, independentemente
da suíte de software e da aceitação do pacote. Ver `tests/acceptance/qualidade.md`.

Gates finais executados: 165/165 testes WSL, 5/5 contratos, 3/3 testes do
instalador, build de 1.929.791.610 bytes e aceitação offline em 32 s. Pacote:
`dist/java-assistente-metodos-linux-x86_64`. Evidências e comandos completos em
`tests/acceptance/checklist.md`. Não houve commit nem substituição do pacote anterior.
