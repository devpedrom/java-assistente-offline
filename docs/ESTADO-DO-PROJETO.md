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

## Integração seletiva — primeiro incremento (2026-11-07)

A branch `integracao/ajustes-main` adapta proteções da versão local sem
substituir `Specification`, solver, adaptadores, perfis ou cenários da main.
O recorte está no [plano de proteções](superpowers/plans/2026-11-06-integracao-main-protecoes.md).

**Portado e ajustado:** leitura/hash/undo preservam bytes UTF-8 e CRLF;
gravações condicionadas recusam conteúdo inesperado, inclusive arquivo criado
durante inferência. A proteção cobre o pedido inteiro (chat e todos os alvos do
solver), é atualizada apenas após escrita bem-sucedida do assistente e encerra
o pedido no conflito, sem restaurar candidatos sobre a edição externa. Classes
temporárias são liberadas na recompilação/fechamento; o runtime é encerrado
mesmo se fechar a sessão falhar.

**Já existente e preservado:** núcleo genérico, classes/interfaces/modificadores,
perfis declarativos, limites, classes locais, verificadores, intake textual e
SQLite atual. Os testes da main continuam presentes; não foram substituídos
pela suíte de outra arquitetura.

**Adiado:** OCR/layout visual, memória portátil e sua migração, correção por
corpos AST e outros incrementos da branch `ajustes-offline-validacao`.
O inventário de escrita não abre `.assistente` e as novas guardas não permitem
usá-lo como alvo; nenhum dado de memória antigo foi convertido ou sobrescrito.

O inventário calcula hashes por pedido, com leitura em blocos. Pastas de
exercício contendo artefatos grandes exigem I/O adicional. As guardas de
conteúdo não são um bloqueio exclusivo do sistema operacional: não substituem
a coordenação entre vários processos que escrevam simultaneamente.

Este incremento não mede a qualidade do modelo. O resultado 14/17 da versão
de origem não é uma aprovação nem uma medição da versão integrada. Nenhum
novo build/bundle, inferência real ou Linux Mint físico foi executado aqui.

### Verificação deste incremento

- Baseline da main `5802591` no Windows:
  `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests -v`
  — 227 executados, 224 aprovados, 3 pulados, nenhuma falha/erro, 120,339 s.
- Suíte final no Ubuntu 24.04/WSL, usando Java e ferramentas do runtime já
  preparado no PATH: `PYTHONPATH=src python3 -m unittest discover -s tests -v`
  — **243 aprovados, 0 falhas/erros, 0 pulados, 82,983 s**. Inclui os caminhos
  Java, instalador Linux e symlink que não foram aprovados pela baseline Windows.
- Revisão independente encontrou três riscos de sobrescrita nas rotas de chat,
  reparo/restauração e alvos posteriores. Foram reproduzidos em regressões antes
  da correção. A suíte final acima foi executada após corrigir os três; nenhuma
  constatação crítica ou menor foi registrada. A assistência de IA abrangeu
  desenho, implementação, testes e revisão; não foram publicadas conversas privadas.
- `git diff --check` foi executado com o Git do Windows. A primeira tentativa
  dessa checagem no WSL falhou após uma suíte verde porque o metadado do worktree
  nativo contém um caminho Windows; não era falha dos testes, nem foi contada
  como aprovação do comando. Os metadados do worktree não foram modificados.
- Packaging não foi alterado; não houve download ou instalação de dependências.
  O bundle anterior não representa automaticamente o código agora integrado.
