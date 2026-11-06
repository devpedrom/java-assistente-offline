# Uso rápido — Assistente Java POO Offline

## Preparação antes da competição

1. Copie a pasta `java-assistente-linux-x86_64` inteira para o pendrive.
2. Confira que ela contém somente `instalar.sh`, `runtime.tar.gz`, `model.gguf` e `manifest.sha256`.

## No computador da competição

1. Copie a pasta `java-assistente-linux-x86_64` do pendrive para `Downloads` no computador.
2. Crie ou abra a pasta vazia onde ficará a solução e coloque o PDF nela.
3. Abra o terminal nessa pasta da solução e execute um único comando: `sh ~/Downloads/java-assistente-linux-x86_64/instalar.sh`.
4. O instalador verifica, copia e abre o chat automaticamente na mesma pasta da solução. Depois disso, o pendrive pode ser removido.
5. Digite `/enunciado`, cole o texto do exercício e termine com `/fim` na última linha; ou use `/pdf`, escolha o número e depois escreva o pedido, por exemplo: `Resolva o exercício em Java POO`.

Depois da primeira instalação, para abrir novamente basta executar `java-assistente` dentro da pasta do exercício.

## Comandos

- `/enunciado`: recebe o enunciado colado como texto; termina com `/fim`.
- `/pdf`: procura PDFs apenas na pasta atual e permite escolher por número.
- `/contrato`: mostra classes, assinaturas, relacionamentos e incertezas reconhecidas.
- `/alteracoes`: mostra o diff das alterações registradas pelo assistente.
- `/estado`: mostra fase, arquivos, última verificação e próxima ação.
- `/memoria`: mostra um resumo limitado do projeto.
- `/desfazer`: desfaz a última alteração do assistente, inclusive após reabrir o projeto, se o arquivo não foi editado depois.
- `/relatorio`: mostra o que veio do PDF/UML, compilou, foi testado e ainda não foi comprovado.
- `/ajuda`: mostra os comandos.
- `/sair`: encerra.

Os critérios gerais ficam em `~/.config/java-assistente/CRITERIOS_GERAIS.md` e são preservados na reinstalação.

Para corrigir uma classe existente, peça `corrija somente Conta`. O assistente
altera um corpo de método por vez e preserva atributos, construtores e assinaturas.
Para restringir a um método, use `corrija somente Conta.total(int)` (informe os
tipos dos parâmetros quando houver sobrecargas). Cada candidato é compilado em
temporário antes de gravar; isso não comprova suas regras de negócio.

A memória acompanha o exercício em `.assistente`. Ao abrir o programa novamente,
o contrato e os resultados ainda válidos são retomados automaticamente; mover a
pasta preserva a identidade. Edições externas, troca de PDF ou de critérios
invalidam as verificações afetadas sem alterar seus fontes. O SQLite é apenas
um cache reconstruível; preserve os JSON/JSONL. A memória global anterior é lida
somente para migração. Não entregue `.assistente` se a competição aceitar apenas fontes.

Os testes locais são casos inferidos pelo modelo, com limites de tempo. Eles
podem identificar erros, mas não garantem cobertura de todas as regras nem
aprovação dos jurados. Confira `/relatorio` e `/contrato` antes de entregar.

Requisito do computador: Linux Mint x86-64 com o `python3` do próprio sistema (3.10 ou superior). Java, modelo, llama.cpp, Poppler e Tesseract seguem dentro do pacote offline.

## Antes de depender do pacote na competição

Execute `tests/acceptance/run-offline.sh` no Linux Mint e preencha `tests/acceptance/checklist.md` no mesmo perfil de hardware. O fluxo com PDF, geração, compilação Java 8 e execução foi verificado no Ubuntu 24.04 via WSL; tempo de cópia do pendrive, consumo em uma máquina com 4–6 GB de RAM e compatibilidade exata com o Linux Mint ainda devem ser medidos no equipamento real.
