# Campos herdados no bloco de declarações — design curto

Data: 2026-10-30. Worktree `java-assistente-offline-opencode`.

## Intenção

O modelo local escolhe `cilindrada` onde a regra manda dividir por
`passageiros`. A informação existe no prompt (19 menções no pedido gravado da
Motocicleta), mas **não** no bloco que o modelo trata como lista autoritativa de
nomes, `DECLARAÇÕES JAVA OBRIGATÓRIAS`, que só lista campos da própria classe.

Além disso, a seção `parents` (fonte da superclasse) é a terceira a ser
descartada pelo orçamento de tokens (`core/budget.py:14`) e foi descartada nesse
pedido. O bloco de contrato nunca é descartado.

## Objetivo

Fazer o campo herdado aparecer no bloco de declarações da unidade filha, com o
dono e a instrução de não redeclarar.

## Não objetivos

- Não alterar verificadores, regras textuais ou o modelo.
- Não reordenar o orçamento de tokens nem remover o texto do PDF.
- Não criar exceção para Frota, Motocicleta ou qualquer exercício.

## Abordagens consideradas

1. **Campos herdados no bloco de declarações** (escolhida): poucas linhas em
   `adapters/java8.py:unit_contract`, derivadas do contrato
   (`spec.relationships` de herança + unidade pai). O bloco é sempre preservado.
2. **Proteger a seção `parents` no orçamento** (não escolhida): mantém o texto
   inteiro da superclasse, mas custa ~700 caracteres num orçamento já estourado
   e mexe na política global de contexto. Fica como próximo passo se a 1 falhar.

## Como fica

Dentro de `DECLARAÇÕES JAVA OBRIGATÓRIAS`, depois das declarações próprias:

```
// herdado de Veiculo, não redeclare:
private int passageiros;
private int combustivel;
private Double rendimento;
```

- Só campos (não métodos herdados), só quando há relação de herança com
  confiança ≥ 0.9 e a unidade pai existe no contrato.
- Nomes, tipos e visibilidade vêm da unidade pai; nada é inferido do texto.

## Risco conhecido

Um modelo de 3B pode copiar a linha e redeclarar o campo. A rodada de validação
mede isso pela compilação e pela nota (Frota 11/17 hoje; Bilhete 7/7 e Reserva
9/9 não podem cair).

## Critério de sucesso

- Teste de unidade do adaptador: filha recebe os campos do pai marcados como
  herdados; unidade sem pai não recebe o bloco.
- Suíte completa verde.
- Rodada real do Frota (seed 42, 5 reparos, 2 threads) comparada com 11/17 e
  com os defeitos atuais; Bilhete e Reserva sem regressão.

## Decisões do implementador

- Reaproveitar `members_of` e as relações do contrato; sem novo módulo.
- A marcação `não redeclare` é texto fixo em português, como o resto do prompt.
