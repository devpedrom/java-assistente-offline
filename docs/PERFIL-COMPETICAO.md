# Perfil de competição

O perfil é o arquivo que ajusta limites, comandos e caminhos técnicos sem alterar
o código do assistente. Ele não ensina regras de negócio e não substitui o PDF
nem o `CRITERIOS_GERAIS.md`.

## Onde fica

1. `~/.config/java-assistente/perfil.json`: perfil global, criado pelo instalador
   somente quando ainda não existe.
2. `<pasta do exercício>/.assistente/perfil.json`: override opcional do projeto,
   lido quando existir. Não é criado automaticamente.

O override é mesclado campo a campo sobre o global; listas substituem, não
concatenam. Reinstalar ou atualizar preserva o arquivo editado.

## O que pode ser ajustado

- `language`: `id` (adaptador) e `source_extension`.
- `toolchain`: caminhos de compilador, runtime e inspetor. Caminhos relativos são
  resolvidos a partir de `JAVA_ASSISTANT_HOME`; absolutos são aceitos.
- `libraries`: lista de `.jar` ou diretórios entregues ao compilador e ao runtime.
- `limits`: timeouts, tentativas de reparo, máximo de arquivos, tokens de contexto
  e de saída.
- `context`: `chars_per_token` e teto de cada seção do contexto.
- `commands`: aliases de `pdf`, `undo`, `report`, `profile`, `help` e `exit`.

O perfil **renomeia ou desabilita** comandos conhecidos; não inventa comportamento
novo. `exit` é obrigatório. Aliases vazios, repetidos ou de comando desconhecido
são recusados na carga, antes do primeiro prompt.

## Limites validados

- `schema_version` exatamente 1; chave desconhecida é erro.
- Timeouts entre 1 e 600 segundos; `repair_attempts` entre 0 e 5.
- `context_tokens` entre 512 e 8192; `output_tokens` entre 64 e 2048 e sempre
  menor que `context_tokens`.
- `chars_per_token` entre 2.0 e 6.0.
- Os caminhos do toolchain e das bibliotecas são verificados ao iniciar, antes do
  primeiro prompt; o erro nomeia o caminho testado.

## Comando `/perfil`

Mostra o caminho do perfil global, o override de projeto (ou `nenhum`), a origem
em uso (`global` ou `project`), o adaptador, os limites efetivos e os aliases
ativos. Não mostra conteúdo de arquivos, credenciais nem caminhos de pendrive.

## Limites desta entrega

- Apenas o adaptador Java 8 é validado; outros `language.id` são recusados.
- O UML **visual** (caixas, setas e posições no desenho) não é interpretado. O
  que vale é o texto do PDF, incluindo a notação textual de classes, membros e
  herança. Relações de composição/agregação não têm notação textual suportada
  nesta versão.
- Compilação e validação estrutural não provam regra de negócio; os testes dos
  jurados continuam fora do alcance do assistente.
