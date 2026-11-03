# Começar uma contribuição com IA

Clone o repositório, abra sua pasta como workspace e forneça o pedido concreto à sua IA. Algumas ferramentas leem `AGENTS.md` automaticamente; em outras, peça a leitura explicitamente. Os arquivos de entrada para Claude, Gemini e Copilot apenas encaminham para as mesmas instruções, evitando cópias divergentes.

## Prompt inicial para copiar

```text
Você vai colaborar neste repositório, um assistente de terminal offline
para exercícios Java POO, voltado a Linux Mint x86-64 e geração Java 8.

Antes de editar:
1. Leia AGENTS.md, README.md e CONTRIBUTING.md na raiz.
2. Leia docs/ARQUITETURA.md e docs/ESTADO-DO-PROJETO.md.
3. Confira git status --short e git diff; preserve mudanças existentes.
4. Leia o código, os testes e a especificação indicados pelo AGENTS.md
   para a área da tarefa. Planos históricos não provam implementação.
5. Resuma seu entendimento e identifique o que será verificado.

Respeite o funcionamento offline, a pasta atual como limite de escrita,
as ações validadas pelo controlador, os timeouts e o alvo Java 8.
Não codifique regras específicas de um exercício no produto.
Não instale, baixe artefatos, faça commits ou publique sem autorização.
Não registre segredos, conversas privadas ou raciocínio interno.

Faça a menor mudança necessária. Execute os testes relevantes e depois
a suíte completa conforme AGENTS.md. Relate comandos, plataforma,
aprovados/falhas/pulos, limitações e pendências. Não declare resultados
de modelo real, Linux Mint ou juiz oficial sem evidência correspondente.

Minha tarefa nesta conversa é: [DESCREVA O PROBLEMA E O RESULTADO ESPERADO].
```

## Leitura por assunto

| Mudança | Leia também |
| --- | --- |
| Controlador, contrato, PDF, Java ou segurança | Especificação principal, módulos afetados e testes de integração |
| Núcleo, perfil ou adaptadores | Design de 2026-10-23, `core/`, `adapters/`, `profile.py` e testes correspondentes |
| Memória entre sessões | Design e plano de memória de 2026-10-22, implementação existente e testes |
| Instalação ou bundle | `docs/USO-RAPIDO.md`, `docs/ARTEFATOS-LINUX.md`, scripts e testes de packaging/aceitação |
| Contexto/prompt do modelo | `core/budget.py`, `core/solver.py`, `session.py`, perfil e testes de geração |

## Ao passar a tarefa para outra pessoa ou IA

Deixe um resumo no PR ou na issue com:

```text
Objetivo e critério de conclusão:
Decisão tomada e motivo:
Arquivos alterados:
Comandos realmente executados e plataforma:
Resultados, falhas e pulos:
O que não foi verificado:
Próximo passo reproduzível:
```

Mantenha contexto compartilhado nos documentos do repositório e no PR, sem depender do histórico privado de uma ferramenta. Um novo colaborador deve conseguir conferir cada afirmação no código ou na evidência indicada.
