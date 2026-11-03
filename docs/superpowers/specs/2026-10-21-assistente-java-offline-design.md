# Assistente Java POO offline para Linux Mint

## 1. Objetivo

Construir uma aplicacao de terminal para Linux Mint que funcione como um assistente de IA local especializado em Java orientado a objetos. A aplicacao deve conversar normalmente, abrir um PDF apenas quando o usuario solicitar, interpretar texto e diagramas UML, criar uma solucao Java em uma pasta vazia, compilar, gerar testes locais, corrigir erros e manter memoria para microajustes.

O pacote sera transportado por pendrive, copiado para o computador e usado sem o pendrive conectado. Instalacao e uso devem funcionar sem internet, APIs externas ou privilegios administrativos.

## 2. Cenario e restricoes

- Sistema-alvo: Linux Mint em computador x86-64.
- Hardware-alvo: processador fraco, 4 a 6 GB de RAM e nenhuma GPU dedicada.
- Entrada da competicao: um PDF e uma pasta vazia.
- Dominio: exercicios de Java POO.
- Conteudo visual esperado: texto e diagramas UML.
- Compatibilidade de codigo: Java 8 por padrao.
- Operacao: totalmente offline no computador da competicao.
- Transporte: pacote completo em pendrive; o uso posterior nao depende dele.
- Interacao: chat de terminal com fluxo hibrido, combinando primeira implementacao automatica e microajustes conversacionais.
- Tempo de preparacao no computador da competicao: no maximo 5 minutos entre executar o instalador e receber o primeiro prompt do chat.

O ZIP do exercicio Frota foi apenas uma amostra de formato. Nenhuma classe, regra, formula ou nome desse exercicio pode ficar codificado na aplicacao.

## 3. Arquitetura escolhida

### 3.1 Inferencia local

Usar `llama.cpp` com o modelo `Qwen2.5-Coder-3B-Instruct` no formato GGUF e quantizacao `Q3_K_M`. O modelo deve ficar no pacote offline e ser substituivel por configuracao, sem alterar o restante da aplicacao. O 3B substitui o 1.5B após o exercício de aceitação demonstrar inconsistência do modelo menor; o bundle continua sujeito ao limite rígido de 2 GB.

A configuracao padrao deve priorizar 4 GB de RAM:

- inferencia somente em CPU;
- contexto conservador e ajustavel;
- quantidade de threads limitada;
- respostas com limite de tokens;
- carregamento sob demanda;
- nenhum segundo modelo residente em memoria.

### 3.2 Controlador deterministico

O modelo nao recebe acesso direto ao shell. Um controlador valida solicitacoes estruturadas e executa apenas ferramentas permitidas. Saidas do modelo que nao atendam ao esquema esperado devem ser rejeitadas ou reparadas antes de qualquer acao.

Ferramentas permitidas:

- ler arquivos autorizados;
- escrever dentro do projeto selecionado;
- criar e modificar fontes Java;
- renderizar e extrair texto do PDF solicitado;
- compilar com o JDK incluido;
- executar Java com limite de tempo e recursos;
- criar testes temporarios separados da entrega;
- mostrar diferencas;
- restaurar uma versao anterior.

Exclusoes, alteracoes em massa e qualquer operacao fora do projeto exigem confirmacao ou devem ser bloqueadas.

### 3.3 Processamento de PDF e UML

O processamento ocorre apenas por solicitacao do usuario. O fluxo deve:

1. extrair a camada textual do PDF;
2. renderizar as paginas relevantes;
3. aplicar OCR quando a camada textual for insuficiente;
4. detectar caixas, compartimentos, conectores e setas de heranca do UML;
5. associar textos as caixas detectadas;
6. produzir um contrato Java estruturado;
7. classificar cada item como confirmado ou inferido;
8. solicitar confirmacao somente para ambiguidades que alterem a implementacao.

O extrator deve reconhecer, quando presentes:

- nomes de classes e interfaces;
- heranca e implementacao de interfaces;
- atributos, tipos e visibilidade;
- construtores;
- metodos, parametros e retornos;
- membros estaticos ou abstratos;
- multiplicidades e associacoes relevantes;
- regras textuais e formulas fora do diagrama.

O contrato extraido deve ser salvo como dado do projeto e permanecer consultavel pelo comando `/contrato`.

#### 3.3.1 PDF misto e classes compiladas na pasta

Quando a camada textual nao traz notacao de membros (`+ metodo(): Tipo`, `- campo: Tipo`) e o PDF possui imagens embutidas, as paginas sao renderizadas a 300 dpi e passam por OCR; o resultado substitui o texto da camada textual e a origem fica registrada como `ocr`, com aviso de conferencia. PDFs so de texto sem diagrama continuam usando a camada textual, sem OCR.

Setas e posicoes do diagrama continuam nao interpretadas. Para recuperar hierarquia e membros que so existem no desenho ou no validador local, o assistente le, com `javap -p` do proprio bundle, as classes `.class` ja presentes na pasta do projeto: apenas as cujo nome aparece no enunciado e que nao declaram `main` (o `main` e tratado como validador/entrada e nunca e sobrescrito). As assinaturas adotadas entram no contrato com confianca `0,98`, rotuladas em `Inferido do UML` como API de classes compiladas da pasta, e a hierarquia inferida substitui relacoes ambiguas do mesmo par. O contrato nao e gerado a partir de bytecode de terceiros; so assinaturas publicas sao lidas.

Depois de compilar, o assistente executa cada classe da pasta que declara `main` como verificador local: primeiro sem argumentos e em modo headless, repetindo uma vez com `--console` se a primeira execucao falhar. Linhas de saida com `❌`, `✘` ou `✗` contam como reprovacao; sem nenhuma linha `✔`/`✓` o resultado nao e considerado aprovado. Se a linha citar o nome de uma unidade do contrato, so essa unidade e regerada, recebendo a linha como diagnostico e respeitando `repair_attempts`; quando a linha nao cita a unidade, vale o ultimo cabecalho de secao (`── ... ──`) que a nomeia. Sem unidade identificavel, nada e reescrito. Enquanto existir verificador local, os fatos aritmeticos textuais (fatores, divisoes nomeadas e limites) orientam uma correcao do modelo; se ainda falharem, o arquivo e mantido, a pendencia fica registrada como nao comprovada e a execucao decide. Um fator so conta no metodo que a regra nomeia e precisa incidir sobre o campo que a regra cita, nao sobre o parametro; a divisao aceita o campo ou o getter dele. Cada rodada corrige todas as unidades reprovadas, nao apenas a primeira. Se a linha reprovada citar excecao, o pedido lembra de validar tambem no construtor, nao so no setter. Sem verificador, esses fatos continuam bloqueando a geracao. Na correcao de compilacao, a primeira tentativa mostra o arquivo atual com o erro e as seguintes pedem reescrita do zero, para o modelo nao copiar a linha quebrada. Nenhum dos dois substitui o juiz da competicao.

## 4. Experiencia no terminal

O usuario primeiro entra na pasta vazia fornecida para a solucao e executa `java-assistente`. A pasta de trabalho atual no momento da inicializacao se torna automaticamente a raiz do projeto e o limite de escrita do agente. Nao existe comando para selecionar outra pasta durante essa sessao.

Exemplo:

```bash
cd /home/aluno/prova
java-assistente
```

O comando `/pdf` nao exige caminho. Ele procura arquivos `.pdf` na raiz da pasta atual e apresenta uma lista numerada, mesmo quando existe apenas um arquivo. O usuario escolhe pelo numero e o sistema inicia imediatamente a extracao de texto e UML.

```text
> /pdf

PDFs encontrados nesta pasta:
1. enunciado-poo.pdf
2. material-de-apoio.pdf

Escolha o PDF: 1
Lendo enunciado-poo.pdf...
```

A busca nao percorre pastas externas nem altera o diretorio do projeto. Se nenhum PDF for encontrado, a aplicacao informa que o arquivo deve ser copiado para a pasta atual.

Depois da leitura, o usuario pode pedir em linguagem natural: `Resolva o exercicio`, `Crie a solucao` ou qualquer microajuste. Linguagem natural e comandos explicitos devem produzir o mesmo resultado.

Comandos minimos:

```text
/pdf
/contrato
/implementar
/compilar
/testar
/revisar
/alteracoes
/desfazer
/criterios
/memoria
/diagnostico
/sair
```

Fluxo principal:

1. o usuario inicia a aplicacao dentro da pasta vazia;
2. usa `/pdf` e escolhe um dos PDFs encontrados na pasta;
3. o assistente apresenta o contrato extraido e incertezas relevantes;
4. o usuario pede a implementacao;
5. o sistema cria as fontes, compila e testa;
6. o assistente entrega um relatorio baseado em evidencias;
7. o chat permanece aberto para microajustes.

O programa nao deve obrigar o usuario a conhecer outros comandos alem de `/pdf`. Depois da selecao do enunciado, pedidos como "crie a solucao" e "corrija somente a classe X" devem acionar os fluxos em linguagem natural.

## 5. Criterios gerais dos jurados

Havera um unico arquivo editavel pelo usuario:

```text
instructions/CRITERIOS_GERAIS.md
```

Na instalacao, ele sera copiado para a configuracao local do usuario. O arquivo deve ser carregado integralmente antes de toda implementacao, revisao ou correcao de codigo. O usuario pode edita-lo com qualquer editor e usar `/criterios` para conferir seu conteudo ou recarrega-lo.

Ordem de precedencia:

1. politicas de seguranca do controlador;
2. `CRITERIOS_GERAIS.md`;
3. requisitos confirmados do PDF;
4. pedido atual do usuario;
5. memoria e decisoes anteriores.

Quando duas fontes entrarem em conflito, o sistema deve mostrar as duas instrucoes e pedir uma decisao. Nao deve escolher silenciosamente.

## 6. Memoria do projeto

A memoria deve ser persistente, leve e independente do caminho de montagem do pendrive. Cada exercicio sera identificado por uma combinacao entre o hash do PDF e um identificador do projeto.

Nao usar banco vetorial. Armazenar dados estruturados pequenos, incluindo:

- resumo do enunciado;
- contrato Java extraido;
- requisitos confirmados e inferidos;
- decisoes do usuario;
- inventario de arquivos;
- ultimo resultado de compilacao;
- testes executados e resultados;
- historico curto de alteracoes;
- resumo compacto da conversa.

Os arquivos do projeto sao a fonte principal da implementacao. A memoria nao pode substituir a releitura dos arquivos afetados por uma correcao.

Antes de modificar um arquivo existente, criar uma copia recuperavel ou registrar um patch reversivel. `/desfazer` deve restaurar a ultima alteracao do assistente sem apagar mudancas anteriores do usuario.

## 7. Implementacao e microajustes

Antes de gerar codigo, o assistente deve montar uma lista verificavel de classes, membros, assinaturas, herancas e comportamentos. A geracao deve preservar exatamente nomes, maiusculas, tipos, visibilidades e assinaturas estabelecidos pelo PDF.

Para cada pedido de correcao:

1. recuperar o contrato e a ultima evidencia de falha;
2. reler somente os arquivos relevantes e suas dependencias;
3. propor ou aplicar a menor mudanca suficiente;
4. mostrar a diferenca;
5. recompilar o conjunto necessario;
6. reexecutar os testes afetados e os controles de regressao;
7. atualizar a memoria.

O assistente nao deve reescrever o projeto inteiro para corrigir uma regra isolada.

## 8. Compilacao, testes e relatorio

Incluir um JDK portatil. O compilador deve gerar codigo compativel com Java 8 por padrao, usando a opcao apropriada do JDK empacotado.

As verificacoes devem cobrir:

### Estrutura

- arquivos publicos e nomes de classes;
- heranca e interfaces;
- atributos, tipos e visibilidade;
- construtores e assinaturas;
- sobrescrita e polimorfismo;
- getters e setters exigidos.

### Compilacao

- compilacao conjunta de todas as fontes;
- diagnosticos apresentados com arquivo e linha;
- tempo limite para evitar travamentos.

### Comportamento

- casos normais derivados das regras do PDF;
- limites e ramificacoes de formulas;
- valores nulos ou invalidos quando mencionados;
- excecoes exigidas;
- uso polimorfico quando aplicavel.

Os testes gerados pelo agente devem permanecer separados dos arquivos de entrega. O agente nunca pode declarar que a solucao passou na avaliacao oficial, pois os testes dos jurados nao estao disponiveis.

O relatorio final deve separar:

```text
CONFIRMADO PELO PDF
INFERIDO DO UML
VALIDADO POR COMPILACAO
VALIDADO POR TESTE LOCAL
AINDA NAO COMPROVADO
```

## 9. Instalacao offline

O pendrive deve conter um pacote autocontido com:

- instalador offline;
- aplicacao;
- modelo GGUF;
- binarios do `llama.cpp` para CPU;
- JDK portatil;
- ferramentas de PDF e OCR;
- arquivo inicial `CRITERIOS_GERAIS.md`;
- manual curto;
- hashes de integridade.

O pacote deve ser preparado previamente, sem compilacao, download ou conversao de modelo durante a instalacao. A distribuicao deve privilegiar poucos arquivos grandes para evitar a lentidao de copiar milhares de arquivos pequenos: um arquivo de runtime compactado, um modelo GGUF ja quantizado, `instalar.sh` e o manifesto. O tamanho total desejado e de ate 1,5 GB; o limite rigido e 2 GB.

O usuario nao precisa copiar manualmente a pasta do programa. Com o pendrive conectado, ele abre um terminal dentro da pasta do pacote e executa um unico comando:

```bash
./instalar.sh
```

Sem fazer perguntas tecnicas, o instalador deve:

1. copiar todos os componentes para diretorios do usuario;
2. criar ou atualizar o comando `java-assistente`;
3. criar `CRITERIOS_GERAIS.md` somente se ele ainda nao existir;
4. preservar criterios, memorias e projetos existentes em uma reinstalacao;
5. ajustar as permissoes dos executaveis incluidos;
6. executar uma verificacao minima e silenciosa dos arquivos essenciais;
7. iniciar automaticamente o chat do assistente quando concluir.

O processo nao exige `sudo`, internet, instalacao de pacotes ou escolha de diretorios. Se ocorrer uma falha, deve mostrar uma mensagem curta com a acao necessaria. Quando o chat abrir, o pendrive pode ser removido.

Em um computador dentro do perfil-alvo e usando USB 2.0 funcional, copia, extracao, verificacao minima e primeira inicializacao devem terminar em ate 5 minutos. O instalador deve mostrar progresso simples e tempo decorrido, sem executar benchmark ou verificacoes demoradas.

Nas utilizacoes seguintes, basta executar:

```bash
java-assistente
```

O diagnostico de hardware sera minimo e local:

- consultar RAM para escolher limites conservadores de contexto;
- detectar AVX/AVX2 para selecionar um binario compativel;
- usar a variante mais conservadora se a deteccao falhar.

Nao realizar benchmark, nao coletar identificadores da maquina e nao enviar dados.

## 10. Tratamento de erros

- PDF ilegivel: indicar paginas afetadas e pedir confirmacao manual.
- UML ambiguo: mostrar interpretacoes concorrentes e nao gerar codigo ate resolver a parte estrutural.
- modelo produz acao invalida: rejeitar a acao e solicitar uma saida estruturada corrigida.
- compilacao falha: preservar os diagnosticos e limitar tentativas automaticas.
- teste excede o tempo: encerrar somente o processo Java iniciado pelo assistente.
- memoria inconsistente: reconstruir o estado a partir do PDF, criterios e arquivos atuais.
- pouco espaco ou RAM: reduzir contexto e interromper com mensagem clara se nao houver execucao segura.

## 11. Criterios de aceitacao da aplicacao

Uma entrega e aceita quando:

1. instala e inicia offline com um unico `./instalar.sh`, sem perguntas tecnicas nem `sudo`;
2. conclui a preparacao e mostra o primeiro prompt do chat em ate 5 minutos no perfil de referencia;
3. continua funcionando depois que o pendrive e removido;
4. inicia um chat local pelo comando `java-assistente`;
5. responde perguntas gerais de Java POO;
6. usa a pasta em que foi iniciado como raiz do projeto e limite de escrita;
7. lista os PDFs dessa pasta ao receber `/pdf` e permite escolher por numero;
8. extrai texto e produz um contrato de um UML de teste;
9. cria uma solucao Java na pasta atual;
10. compila e executa testes locais com o JDK incluido;
11. aplica `CRITERIOS_GERAIS.md` em implementacoes e revisoes;
12. preserva memoria entre reinicializacoes;
13. executa um microajuste sem reescrever arquivos nao relacionados;
14. desfaz a ultima alteracao do assistente;
15. bloqueia escrita fora do projeto;
16. nao realiza conexoes de rede durante instalacao ou uso;
17. apresenta evidencias honestas sobre o que foi ou nao validado.

## 12. Fora de escopo

- linguagens diferentes de Java;
- desenvolvimento web, Android ou interfaces graficas;
- avaliacao oficial dos jurados;
- acesso a internet ou APIs de IA;
- execucao diretamente do pendrive;
- suporte geral a qualquer tipo de diagrama ou imagem;
- treinamento ou ajuste fino do modelo durante a competicao.

