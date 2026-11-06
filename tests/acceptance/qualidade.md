# Fidelidade ao enunciado

Régua do assistente: cada enunciado de `tests/fixtures/enunciados/` tem um
contrato esperado em `expected/<nome>.json`. O medidor compara o contrato
extraído com o esperado e, quando recebe `--solucao`, compila e executa.

```sh
PYTHONPATH=src python3 tests/qualidade/medir.py
PYTHONPATH=src python3 tests/qualidade/medir.py --fixture E5 --solucao /caminho/da/solucao
```

## O que cada fixture prova

| Fixture | Entrada | O que prova |
|---|---|---|
| E1 | texto, herança + regra de porcentagem, sem pedir `main` | entende enunciado em texto e não inventa classe de teste |
| E2 | texto em lista, sem a palavra `class` | entende enunciado escrito de outro jeito |
| E3 | texto, 3 classes, associação + "nunca pode ser maior que" | respeita regra de negócio |
| E4 | PDF sintético com o conteúdo de E1 | a entrada por PDF continua funcionando |
| E5 | PDF e validador reais em `tests/fixtures/frota/` | bateria fornecida da disciplina, não os testes secretos |

E5 compara o contrato completo (`contract_scope: full`), incluindo membros,
tipos, visibilidades e herança. O `--solucao` roda o validador fornecido
`Frota --console`, com prioridade no classpath, e exige as 17 linhas positivas
e o delimitador final em UTF-8, além de exit code zero.

Os registros datados abaixo são históricos; o estado mais recente está no
complemento de 2026-11-06 ao final deste documento.

## Linha de base — 2026-11-04

Comando: `python tests/qualidade/medir.py` (Windows, sem pdftotext e sem o modelo).

```
E1  contrato: ok      compilado: não medido  comportamento: não medido
E2  contrato: FALHOU  compilado: não medido  comportamento: não medido  (nenhuma classe reconhecida)
E3  contrato: ok      compilado: não medido  comportamento: não medido
E4  contrato: não medido  (pdftotext ausente)
E5  contrato: não medido  (pdftotext ausente)

Fidelidade: 2 de 5
```

- **2 de 5 medidos**, ambos aprovados; E2 falha como esperado, porque o
  extrator atual exige a palavra `class`/`classe` (corrigido na Task 6).
- **E4 e E5 não medidos aqui:** esta máquina não tem `pdftotext`. A medição
  vale em Linux Mint ou WSL com Poppler, junto da aceitação.
- **Compilação e comportamento não medidos:** pertencem ao juiz próprio
  (Task 8). Até lá, o único comportamento automatizado é `Frota --console`
  com `--solucao`, que exige uma solução em `.java`.
- A cópia do desafio em `tests/fixtures/frota/` é fixture de teste, nunca
  código do produto.

## Nova medição — 2026-11-04

Ubuntu 24.04/WSL, `PYTHONPATH=src python3 tests/qualidade/medir.py`, com Poppler
do runtime já empacotado no PATH (sem instalar ou baixar ferramentas):

```text
E1  contrato: ok      compilado: não medido  comportamento: não medido
E2  contrato: ok      compilado: não medido  comportamento: não medido
E3  contrato: ok      compilado: não medido  comportamento: não medido
E4  contrato: ok      compilado: não medido  comportamento: não medido
E5  contrato: FALHOU  compilado: não medido  comportamento: não medido (nenhuma classe reconhecida)

Fidelidade: 4 de 5
```

Comparação: a linha de base Windows tinha 2 contratos aprovados, E2 falhando e
E4/E5 não medidos. Agora E2 passa; E4 passa no WSL. A comparação entre sistemas
não prova que E4 foi corrigido nesta mudança. E5 continua sem contrato: o fluxo
recusa gerar uma solução a partir de um contrato vazio. **A meta de fidelidade
completa ainda não foi atingida.**

Os testes do juiz local exercitam compilação Java 8, retorno boxed exato,
construtores, composição de efeitos, exceção obrigatória e observação de estado
após método void. As propostas do modelo são inferências, não um oráculo oficial.
Argumentos de associação/objetos ainda são reportados como não comprovados.

`bash tests/acceptance/validator.sh <pasta-da-solucao>` executa o validador real
em temporário com timeout e não aceita saída `FALHOU` mesmo com exit code zero.
O teste automatizado do script cobre essa recusa. Não há solução E5 gerada e
validada nesta medição; a bateria oficial permanece **não executada**.

## Complemento — 2026-11-05 (conclusão em andamento)

- O PDF E5 tem texto para as regras e uma imagem para o UML. A extração agora
  detecta caixas, faz OCR separado e segue conectores com seta; conectores
  incertos exigem confirmação. Caixas parcialmente ilegíveis são recusadas
  explicitamente, sem apresentar um contrato parcial como completo.
- A régua nativa passou **5/5 contratos**, agora comparando também os membros,
  tipos e visibilidades de E5. A fixture antiga tinha visibilidades privadas
  incorretas: a imagem mostra campos protegidos na classe-base e no câmbio.
  Construtores necessários de subclasses são inferidos e identificados como tal.
- Foram acrescentados oráculos finitos independentes para E1/E4: um saldo de
  100 deve virar 102 após `render()`, conforme os 2% declarados. Não dependem
  das expectativas inventadas pelo modelo. Uma implementação que compila mas
  não atualiza o saldo foi rejeitada pelo teste de regressão.
- O validador real precisa ter prioridade no classpath sobre o `main` gerado.
  Além disso, ele termina com exit0 mesmo quando imprime `❌`/`FALHA`; a
  aceitação compartilhada agora exige as 17 linhas positivas e o delimitador
  final, em UTF-8. Uma implementação numericamente errada foi rejeitada, e as
  classes de referência da fixture foram aceitas. Essas referências são usadas
  **somente para testar o verificador**, nunca copiadas para a solução gerada.
- A primeira geração real criou/reparou as classes, mas o reinício do WSL
  interrompeu os testes locais e apagou o projeto temporário. A nova execução
  persiste os fontes e a memória em `.superpowers/.../real-solutions/E5` e pode
  retomar sem regenerar arquivos concluídos. **Ainda não há aprovação do E5
  gerado para registrar nesta seção.**
- A suíte final e a atualização do pacote devem ocorrer após a execução real;
  testes dirigidos de correção passaram, mas o último teste completo Windows
   concorrente com inferência excedeu o timeout e não conta como aprovação.

## Complemento — 2026-11-06 (correção por método)

- Contratos E1–E5: **5/5 conferidos** no Ubuntu 24.04/WSL com as ferramentas do
  runtime. Compilação/comportamento de E1–E4 não foram medidos nessa régua.
- A correção de classe existente agora pede somente corpos, localiza seus
  intervalos pela AST do JDK e valida cada candidato em temporário antes de
  gravar pelo histórico. Construtores, assinaturas e outros arquivos são preservados.
- Revisão independente: quatro achados importantes reproduzidos e corrigidos
  com regressões (sobrecargas case-sensitive, restrição de método, recuperação
  do histórico e PDF misto). Nenhum achado crítico ou menor registrado.
- O modelo real finalmente retornou os corpos no protocolo correto, mas
  repetiu a lógica incorreta. A bateria fornecida continua **14/17**: autonomia
  automática de Hatch retorna 405 em vez de 450 e volumes com quatro/cinco
  passageiros retornam zero em vez de 300. **A aceitação real não está concluída.**
- Nenhum Java da solução foi corrigido à mão. Os hashes dos seis arquivos
  permaneceram iguais ao início desse reteste. Propostas de testes locais do
  modelo tiveram lista inválida; foram contabilizados zero casos inferidos
  aprovados, sem transformar compilação em prova de regras de negócio.
- Logs e evidências de testes/pacote:
  `.superpowers/sdd/2026-11-06-correcao-por-metodo/`. Gates finais de software
  e pacote são registrados no checklist; não substituem o gate real reprovado.
