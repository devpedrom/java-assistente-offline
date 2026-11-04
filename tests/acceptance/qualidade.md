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
| E5 | PDF e validador reais em `tests/fixtures/frota/` | aprovação no juiz da disciplina |

E5 compara nomes de classe e herança (`contract_scope: names`): os membros do
diagrama só podem ser conferidos com o texto real extraído no Linux. O
`--solucao` de E5 roda `Frota --console` e exige saída sem `FALHOU`.

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
