# Uso rápido — Assistente Java POO Offline

## Preparação antes da competição

1. Copie a pasta `java-assistente-linux-x86_64` inteira para o pendrive.
2. Confira que ela contém somente `instalar.sh`, `runtime.tar.gz`, `model.gguf` e `manifest.sha256`.

## No computador da competição

1. Copie a pasta do pendrive para o computador.
2. Abra o terminal dentro dessa pasta e execute: `./instalar.sh`.
3. O instalador verifica, copia e abre o chat automaticamente. Depois disso, o pendrive pode ser removido.
4. Vá até a pasta vazia da solução, coloque o PDF nela e execute `java-assistente`.
5. Digite `/pdf`, escolha o número e depois escreva o pedido, por exemplo: `Resolva o exercício em Java POO`.

## Comandos

- `/pdf`: procura PDFs apenas na pasta atual e permite escolher por número.
- `/desfazer`: desfaz a última alteração do assistente se o arquivo não foi editado depois.
- `/relatorio`: mostra o que veio do PDF/UML, compilou, foi testado e ainda não foi comprovado.
- `/ajuda`: mostra os comandos.
- `/sair`: encerra.

Os critérios gerais ficam em `~/.config/java-assistente/CRITERIOS_GERAIS.md`. Reinstalar ou atualizar não sobrescreve esse arquivo nem a memória em `~/.local/state/java-assistente`.
