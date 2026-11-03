# Estado do projeto e próximos passos

Referência de organização: 2026-11-03. Este documento aponta fontes verificáveis e deve ser atualizado quando o comportamento mudar.

## Implementação disponível

O código contém CLI, perfil declarativo, núcleo de contrato/planejamento, adaptador Java 8, integração com modelo local, extração de PDF/OCR, geração e reparo, ferramentas Java, histórico e relatório de evidências. Consulte [arquitetura](ARQUITETURA.md) e testes para o alcance de cada parte.

Há memória SQLite em `memory/store.py`. O design de memória portátil entre sessões não está automaticamente implementado por existir um diretório `.assistente` para override de perfil.

## Evidências e limites

O [registro de aceitação](../tests/acceptance/checklist.md) contém execuções anteriores de Windows, WSL e bundle, identificadas por data e hash. Alguns logs completos estão em `work/`, ignorado pelo Git, e não acompanham o clone público. Esses registros históricos não substituem uma nova execução da suíte e do bundle após alterações.

A qualidade do modelo real varia conforme o exercício. Fixtures com respostas preparadas são testes do fluxo; não comprovam resolução geral. Não há acesso aos testes oficiais de jurados.

## Trabalho a avaliar com o responsável

- Medir instalação, pico de memória, compatibilidade de CPU e cópia USB em Linux Mint físico com 4–6 GB de RAM.
- Investigar regressões de geração com casos reproduzíveis e exercícios diversos, preservando a generalidade do produto.
- Evoluir reconhecimento de UML visual; hoje caixas, setas e posições não têm interpretação completa.
- Implementar a memória portátil somente com base no design/plano e em testes de aceitação próprios.
- Conferir licenças e avisos de terceiros antes de distribuir binários e modelo.

Esses pontos são pendências e oportunidades de contribuição, não promessa de entrega ou autorização para uma reescrita. Combine uma tarefa pequena na issue e registre evidência ao concluí-la.
