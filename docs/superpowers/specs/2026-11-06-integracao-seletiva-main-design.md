# Integração seletiva dos ajustes à main pública

## Objetivo e aprovação da abordagem

O usuário escolheu adaptar os ajustes do commit `ef57eb8` à arquitetura da
`main` pública, preservando suas funcionalidades. A branch de origem já está
publicada como `ajustes-offline-validacao`. Este desenho detalha essa escolha;
ainda não autoriza substituir arquivos conflitantes em bloco.

Bases inspecionadas: `main` em `5802591` e origem em `ef57eb8`. Não possuem
ancestral comum; uma prévia de merge encontrou 38 conflitos. A integração terá
como ancestral a main e será feita em `integracao/ajustes-main`, num worktree
separado. Edições não commitadas no checkout original ficam fora da integração.

## Abordagens

- **Substituir a main pela versão local:** rejeitada; removeria núcleo,
  adaptadores, perfis, cenários e documentação já existentes.
- **Mesclar todos os arquivos e escolher um lado dos conflitos:** rejeitada;
  os nomes de arquivo iguais escondem APIs e comportamentos distintos.
- **Adaptar seletivamente:** escolhida pelo usuário. Preserva a main como
  base e porta somente melhorias demonstráveis, com regressões e inventário.

## Contratos de integração

1. `core.spec.Specification`, `Unit` e `Member` continuam como modelo de
   contrato. Não introduzir `JavaContract` nem outra representação concorrente.
2. `core/solver.py`, `adapters/`, `profile.py`, os limites declarativos e o
   fluxo de confirmação permanecem ativos. Melhorias Java ficam no adaptador
   Java/toolchain ou num auxiliar chamado explicitamente pelo controlador.
3. Preservar suporte atual a interfaces, modificadores, composição, classes
   locais, verificadores e intake textual. Não copiar o `session.py` antigo.
4. Reutilizar verificadores e evidências existentes. Não acrescentar um segundo
   juiz só para reproduzir a origem; exit zero sozinho não prova comportamento.
5. Offline, Java 8, raiz imutável, timeouts e ausência de shell para o modelo
   permanecem invariantes. Sem dependências, modelo ou binários novos.

## Entregas incrementais propostas

### A — Proteções compartilhadas

Portar preservação de bytes CRLF/UTF-8, checagem do conteúdo esperado antes de
escrever, limpeza de classes temporárias e encerramento do runtime mesmo se a
sessão falhar ao fechar. Atualizar todos os chamadores no controlador e solver,
sem trocar seus protocolos. Cada melhoria já existente será apenas registrada.

### B — Evidência PDF/UML

Acrescentar análise de caixas/conectores e OCR recortado, preservando a camada
textual para regras. Representar a estrutura reconhecida no contrato genérico
existente. OCR mantém confiança inferior e exige confirmação; caixas incompletas
ou conflito de tipos não podem produzir contrato silenciosamente completo.
Preservar `pdfimages` e o caminho barato de PDFs realmente só textuais.

### C — Continuidade e correções Java

Adaptar a memória portátil ao `Specification` e à configuração relevante do
perfil, sem remover o override `.assistente` existente. Preservar UUID, JSON
canônicos, cache reconstruível, retomada e invalidação por edição externa/PDF/
critérios/perfil. Formatos incompatíveis devem ser detectados, não reinterpretados.
Histórico reversível será persistido antes da gravação do fonte.

Adaptar o auxiliar AST de corpos ao contrato genérico e ao classpath/timeouts
do perfil. Usar corpos somente em correção comportamental de Java existente;
geração inicial e reparo estrutural continuam com o solver atual. Pedido de um
método preserva os demais, sobrecargas são case-sensitive, candidatos compilam
em temporário e edição concorrente impede a gravação. O adaptador de teste e
as outras rotas não passam a exigir um JDK para tarefas puramente Python.

Essas entregas serão planejadas separadamente e executadas nessa ordem. Uma
entrega verde pode ser publicada sem anunciar as próximas como implementadas.

### Recorte autorizado para começar

Após a recomendação de preservar memórias antigas e adiar sua conversão, o
usuário respondeu “prossiga”. O primeiro incremento é somente **A — Proteções
compartilhadas**. B e C permanecem próximas etapas, não entregas deste incremento.
Não abrir, converter, substituir ou excluir `.assistente` nem importar eventos
SQLite antigos. Ao planejar C, definir um formato distinto/detectável e pedir
aprovação específica caso seja necessário migrar memórias entre arquiteturas.

## Testes e publicação

- Medir a suíte da main antes de mudar código; falhas preexistentes e pulos
  ficam separados de regressões introduzidas.
- Testes dirigidos RED→GREEN e suíte completa após cada entrega. Preservar todos
  os testes da main; não substituí-los pelos 165 testes da branch antiga.
- Usar fixtures sintéticas próprias para a integração pública. Não acrescentar
  PDFs/bytecode do desafio, modelos, bundles, memórias, logs privados ou dados locais.
- Mudanças de packaging exigem testes do instalador, build com artefatos já
  preparados e aceitação Linux/WSL. Não instalar nem baixar dependências.
- Revisar uma vez o conjunto adaptado. Publicar a branch descendente da main e
  só integrar à main após evidência verde e nova conferência do remoto, sem force.
  Se a main avançar, reavaliar a integração; não substituir o avanço remoto.
- Registrar inventário de itens portados, já existentes e adiados, comandos,
  plataforma e resultados no PR/documentação. Nada autoriza prometer 17/17:
  a origem permanece em 14/17 e seus testes não certificam a versão integrada.
- Um PR intermediário pode ser publicado como rascunho com pendências visíveis.
  Merge requer regressões e suíte completas verdes no WSL com as ferramentas
  existentes; pulos de ferramenta/instalador/symlink do Windows não contam como
  aprovação desses caminhos. Mint físico e modelo real são limites explicitados,
  não requisitos presumidamente aprovados nem bloqueio para preparar o PR.

## Limites não removidos

Linux Mint físico 4–6 GB, consumo/CPU/USB, inferência real da versão integrada
e testes secretos só serão declarados verificados mediante nova execução.
Não garantir automaticamente compatibilidade de memória entre as duas
arquiteturas: escolher e testar o formato/migração antes de portar a entrega C.
