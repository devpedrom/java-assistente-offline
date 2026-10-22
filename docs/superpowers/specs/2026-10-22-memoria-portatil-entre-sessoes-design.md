# Memoria portatil entre sessoes

## 1. Objetivo

Permitir que o Assistente Java POO Offline seja encerrado e iniciado novamente
na mesma pasta de exercicio sem perder requisitos, decisoes, progresso,
diagnosticos ou evidencias. A retomada deve ser automatica e usar somente o
modelo local ja incluido no pacote.

A memoria pertence ao projeto, nao a uma conversa nem ao modelo. O usuario nao
deve precisar exportar, copiar ou colar contexto para continuar o trabalho.

## 2. Escopo aprovado

- Persistir o estado dentro de uma pasta oculta `.assistente` na raiz do
  exercicio.
- Retomar automaticamente o projeto ao executar `java-assistente` novamente na
  mesma pasta.
- Continuar usando exclusivamente o runtime e o modelo local atualmente
  empacotados.
- Manter o funcionamento totalmente offline.
- Nao integrar Graphify.
- Nao implementar adaptadores, seletores ou compatibilidade com outros modelos.
- Nao usar banco vetorial, servico externo ou processo residente adicional.

Esta entrega melhora continuidade e recuperacao. Ela nao substitui compilacao,
testes, validacao do contrato UML ou revisao das regras do enunciado, e nao cria
uma garantia de aprovacao em testes secretos dos jurados.

## 3. Fonte de verdade

A fonte de verdade sera composta por arquivos pequenos e versionados por
esquema:

```text
<projeto>/
├── enunciado.pdf
├── *.java
└── .assistente/
    ├── projeto.json
    ├── requisitos.json
    ├── estado.json
    ├── decisoes.jsonl
    ├── verificacoes.json
    ├── contexto.md
    ├── proxima_acao.md
    ├── memoria.db
    └── recuperacao/
```

Responsabilidades:

- `projeto.json`: versao do esquema, identificador persistente, PDF ativo e
  hashes dos artefatos essenciais.
- `requisitos.json`: contrato Java e requisitos extraidos do PDF, com origem,
  confianca e situacao de validacao.
- `estado.json`: fase atual, arquivos conhecidos, classe em andamento,
  pendencias e ultima operacao concluida.
- `decisoes.jsonl`: diario somente de acrescimo com decisoes, suposicoes,
  correcoes e resultados relevantes.
- `verificacoes.json`: ultima compilacao, inspecao estrutural, execucao e testes,
  sempre ligados ao hash dos arquivos verificados.
- `contexto.md`: resumo curto e regeneravel para a proxima chamada ao modelo.
- `proxima_acao.md`: instrucao objetiva de retomada.
- `memoria.db`: indice SQLite para consultas rapidas. Ele e cache reconstruivel,
  nao a unica copia dos fatos.
- `recuperacao/`: ultimo estado consistente necessario para desfazer uma escrita
  interrompida ou um microajuste.

Nao armazenar raciocinio privado do modelo. Registrar apenas requisitos,
decisoes, resultados, evidencias, erros e proximas acoes verificaveis.

## 4. Identidade do projeto

Na primeira execucao, o controlador cria um identificador aleatorio em
`projeto.json`. O identificador acompanha a pasta caso ela seja movida ou
renomeada. O hash do PDF identifica a versao do enunciado, mas nao substitui o
identificador, pois dois projetos podem usar o mesmo PDF.

Ao iniciar:

1. usar a pasta atual como raiz protegida;
2. localizar `.assistente/projeto.json`;
3. validar versao do esquema e integridade minima;
4. comparar o hash atual do PDF e dos fontes com os hashes persistidos;
5. reconstruir caches ou invalidar evidencias antigas quando houver mudanca;
6. montar o contexto curto;
7. informar em uma linha que o projeto foi retomado e qual e a proxima acao.

Uma copia da pasta preserva a memoria junto do codigo. Duas copias modificadas
separadamente passam a ser projetos divergentes; o controlador nao tentara
mescla-las automaticamente.

## 5. Escrita transacional

Cada mudanca de estado deve seguir esta ordem:

1. preparar o novo conteudo sem alterar o estado valido;
2. escrever em arquivo temporario dentro de `.assistente`;
3. validar JSON, campos obrigatorios e referencias;
4. sincronizar e substituir atomicamente o arquivo de destino;
5. acrescentar o evento correspondente em `decisoes.jsonl`;
6. atualizar `estado.json` por ultimo.

Se o processo for interrompido, a proxima inicializacao deve escolher o ultimo
estado integralmente valido. Arquivos `.java` modificados devem continuar
protegidos pelo mecanismo de desfazer ja existente.

O diario tera identificador do evento, horario local, tipo, arquivos afetados,
resultado e hashes antes/depois. Nao armazenar senha, nome da maquina, caminho
do pendrive ou identificadores desnecessarios do computador.

## 6. Retomada e contexto do modelo

O modelo nao recebera todo o historico. O controlador montara uma janela curta
com:

1. criterios gerais atuais;
2. requisitos relevantes para a tarefa corrente;
3. contrato das classes envolvidas;
4. fontes Java diretamente relacionadas;
5. ultima evidencia de falha ou sucesso;
6. decisoes ainda vigentes;
7. proxima acao.

O resumo sera regenerado a partir dos dados estruturados. `contexto.md` acelera
a retomada, mas nunca prevalece sobre o PDF, o contrato, os fontes ou resultados
de ferramentas.

Depois de cada classe criada, correcao aplicada, compilacao, validacao estrutural
ou teste, o estado deve ser persistido antes da proxima chamada ao modelo. Assim,
uma interrupcao perde no maximo a resposta ainda nao validada.

## 7. Reconciliacao com alteracoes externas

O usuario pode editar arquivos Java com outro editor enquanto o assistente esta
fechado. Na retomada:

- fonte com hash diferente e marcado como alterado externamente;
- evidencias ligadas ao hash anterior ficam invalidas;
- o arquivo do usuario nunca e sobrescrito apenas para igualar a memoria;
- o controlador recompila e reinspeciona antes de considerar o estado valido;
- requisitos e decisoes permanecem, salvo conflito comprovado.

Se o PDF mudar, o controlador preserva o diario anterior, cria uma nova versao
do contrato e exige nova validacao das classes afetadas.

## 8. Recuperacao de inconsistencias

Falhas devem ser tratadas nesta ordem:

1. validar os arquivos JSON atuais;
2. recuperar a ultima copia consistente;
3. reproduzir o diario de eventos valido;
4. reconstruir `memoria.db`;
5. reextrair o PDF somente se os dados estruturados nao puderem ser recuperados;
6. recompilar e reinspecionar os fontes atuais.

Nenhuma inconsistencia de memoria autoriza apagar ou reescrever fontes Java. Se
a recuperacao automatica nao for segura, o assistente deve preservar os arquivos
e explicar objetivamente qual estado nao pode ser comprovado.

## 9. Experiencia do usuario

O fluxo normal continua com um comando:

```bash
cd /caminho/do/exercicio
java-assistente
```

Primeira sessao:

```text
Novo projeto iniciado nesta pasta.
Use /pdf para escolher o enunciado.
```

Sessoes seguintes:

```text
Projeto retomado: 5 classes, ultima compilacao aprovada.
Proxima etapa: validar os casos de limite de Pickup.
```

O comando `/memoria` mostrara um resumo legivel, sem despejar o banco ou o
historico completo. Um novo comando `/estado` mostrara fase, PDF, arquivos,
ultima verificacao e proxima acao.

O usuario nao precisara executar um comando de salvar. `/sair` fara uma ultima
validacao do estado, mas o progresso ja estara persistido continuamente.

## 10. Integracao com a implementacao existente

A mudanca deve reutilizar:

- `MemoryStore` para o indice SQLite;
- o contrato produzido pelo extrator UML;
- os resultados de `JavaToolchain` e `ContractValidator`;
- o historico reversivel do workspace;
- a restricao que impede caminhos fora da raiz do projeto.

A persistencia global atualmente localizada no diretorio do usuario podera ser
lida durante a migracao, mas novos projetos gravarao seu estado canonico em
`.assistente`. Dados globais de configuracao, como `CRITERIOS_GERAIS.md`,
continuam fora do projeto.

A integracao nao deve mudar o modelo GGUF, iniciar um segundo modelo ou aumentar
o contexto padrao apenas porque existe mais historico.

## 11. Testes obrigatorios

### Unidade

- serializacao e validacao de cada esquema;
- substituicao atomica;
- diario somente de acrescimo;
- deteccao de hashes alterados;
- selecao do contexto relevante;
- reconstrucao do SQLite a partir dos arquivos canonicos.

### Integracao

- iniciar projeto, carregar PDF, criar uma classe, encerrar e retomar;
- interromper durante uma escrita e recuperar o ultimo estado valido;
- editar um `.java` externamente e invalidar somente as evidencias afetadas;
- mover a pasta e preservar a identidade;
- trocar o PDF e versionar o contrato;
- corromper `memoria.db` e reconstrui-lo sem perder decisoes;
- confirmar que nenhuma escrita escapa da raiz;
- confirmar que nenhuma conexao de rede ocorre.

### Aceitacao no Linux

Em uma instalacao limpa, executar um exercicio ate uma etapa intermediaria,
encerrar o processo, abrir outra sessao na mesma pasta e concluir a solucao sem
repetir `/pdf`, requisitos ou correcoes ja registradas.

## 12. Criterios de aceitacao

A funcionalidade sera aceita quando:

1. uma nova sessao reconhece automaticamente um projeto existente;
2. a retomada nao exige texto copiado da sessao anterior;
3. requisitos, decisoes, erros e verificacoes permanecem disponiveis;
4. evidencias antigas sao invalidadas quando os fontes mudam;
5. uma interrupcao nao corrompe o ultimo estado valido;
6. o banco SQLite pode ser reconstruido;
7. mover a pasta nao perde a identidade nem a memoria;
8. o contexto enviado ao modelo permanece limitado ao necessario;
9. o funcionamento continua offline e dentro do limite de hardware;
10. a entrega nao inclui Graphify nem suporte a outros modelos.

## 13. Fora de escopo

- Graphify, Graphiti, banco de grafos ou banco vetorial;
- sincronizacao entre computadores;
- mesclagem automatica de copias divergentes;
- compartilhamento de memoria entre projetos;
- importacao de conversas do Codex ou de outros chats;
- selecao, troca ou roteamento entre modelos;
- compatibilidade garantida com agentes externos;
- armazenamento de raciocinio privado do modelo;
- garantia de aprovacao nos testes secretos dos jurados.
