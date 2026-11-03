# Uso rápido — Assistente Java POO Offline

## Preparação antes da competição

1. Copie a pasta `java-assistente-linux-x86_64` inteira para o pendrive.
2. Confira que ela contém somente `instalar.sh`, `runtime.tar.gz`, `model.gguf` e `manifest.sha256`.

## No computador da competição

1. Copie a pasta `java-assistente-linux-x86_64` do pendrive para `Downloads` no computador.
2. Crie ou abra a pasta vazia onde ficará a solução e coloque o PDF nela.
3. Abra o terminal nessa pasta da solução e execute um único comando: `sh ~/Downloads/java-assistente-linux-x86_64/instalar.sh`.
4. O instalador verifica, copia e abre o chat automaticamente na mesma pasta da solução. Depois disso, o pendrive pode ser removido.
5. Digite `/pdf`, escolha o número e depois escreva o pedido, por exemplo: `Resolva o exercício em Java POO`.

Depois da primeira instalação, para abrir novamente basta executar `java-assistente` dentro da pasta do exercício.

## Comandos

- `/pdf`: procura PDFs apenas na pasta atual e permite escolher por número.
- `/desfazer`: desfaz a última alteração do assistente se o arquivo não foi editado depois.
- `/relatorio`: mostra o que veio do PDF/UML, compilou, foi testado e ainda não foi comprovado.
- `/perfil`: mostra o perfil em uso, os limites e os comandos ativos.
- `/ajuda`: mostra os comandos.
- `/sair`: encerra.

Os critérios gerais ficam em `~/.config/java-assistente/CRITERIOS_GERAIS.md`. Reinstalar ou atualizar não sobrescreve esse arquivo nem a memória em `~/.local/state/java-assistente`.

O perfil técnico fica em `~/.config/java-assistente/perfil.json` e é criado pelo instalador apenas se ainda não existir. Um override opcional em `<pasta do exercício>/.assistente/perfil.json` ajusta limites, caminhos e aliases só naquele projeto. Detalhes em `docs/PERFIL-COMPETICAO.md`; reinstalação também preserva o perfil editado.

O assistente interpreta o texto do PDF e a notação textual de classes, membros e herança. O UML **visual** (caixas, setas e posições no desenho) não é interpretado nesta versão.

Quando o PDF mistura texto e diagrama em imagem, a página é lida por OCR e a origem aparece como `ocr` em `/relatorio`; nomes e símbolos devem ser conferidos. Se a pasta do exercício já trouxer classes `.class` (validador ou classes de referência), o assistente lê apenas as assinaturas públicas dessas classes com o `javap` do pacote e as usa para completar o contrato, registrando isso como **Inferido do UML**. Classes com `main` não são adotadas nem sobrescritas.

Depois de compilar, o assistente roda essas classes com `main` como verificador local (headless e, se precisar, com `--console`). Linhas com `❌`, `✘` ou `✗` reprovam; sem nenhuma linha `✔`, nada é considerado aprovado. Se a linha citar uma classe do contrato, só ela é gerada de novo com a linha como erro; se não citar, vale o último cabeçalho de seção (`── ... ──`) que a nomeia. Sem classe identificável, nada é reescrito e o relatório mostra a saída. Com verificador local, os fatores do enunciado orientam uma correção do modelo e, se ainda falharem, o arquivo é mantido, a pendência fica registrada e a execução decide; sem verificador, os fatores continuam bloqueando. Cada rodada corrige todas as classes reprovadas, e uma falha que cita exceção lembra de validar também no construtor. A bateria aprovada aparece em **Testado localmente** e não equivale ao juiz da competição. Na correção de compilação, a primeira tentativa mostra o arquivo atual e as seguintes pedem reescrita do zero, para o modelo não repetir a linha quebrada.

Durante as correções dos verificadores locais, o assistente preserva conjuntos completos de fontes já compilados e avaliados. Se precisar restaurar o conjunto com o melhor indicador local de aprovações/reprovações, ele recompila, confere a estrutura e executa os verificadores novamente. O relatório mostra as falhas dessa reavaliação. Um resultado parcial continua sendo uma pendência; a contagem de linhas do verificador não prova aprovação no juiz da competição.

O contrato da classe alvo e o pedido atual são preservados integralmente no contexto enviado ao modelo, usando espaço das seções opcionais quando necessário. Se o conteúdo obrigatório não couber no orçamento estimado, a geração para com um erro explícito. Isso evita perder requisitos silenciosamente, mas não garante que o modelo os implemente corretamente.

Requisito do computador: Linux Mint x86-64 com o `python3` do próprio sistema (3.10 ou superior). Java, modelo, llama.cpp, Poppler e Tesseract seguem dentro do pacote offline.

## Antes de depender do pacote na competição

Execute `tests/acceptance/run-offline.sh` no Linux Mint e preencha `tests/acceptance/checklist.md` no mesmo perfil de hardware. O fluxo com PDF, geração, compilação Java 8 e execução foi verificado no Ubuntu 24.04 via WSL; tempo de cópia do pendrive, consumo em uma máquina com 4–6 GB de RAM e compatibilidade exata com o Linux Mint ainda devem ser medidos no equipamento real.
