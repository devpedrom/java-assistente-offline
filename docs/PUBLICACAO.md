# Preparação da primeira publicação pública

Destino autorizado: `devpedrom/java-assistente-offline`, público. Licença pendente por decisão do responsável. O repositório foi criado em 2026-11-03; a confirmação do envio é feita pelo commit remoto e pela página pública.

## Conteúdo preparado

- README com objetivo, início rápido, limites e índice de documentos.
- Guia de contribuição, arquitetura, estado e roteiro de contexto para IA.
- `AGENTS.md` como fonte central, com referências em `CLAUDE.md`, `GEMINI.md` e instruções do Copilot.
- Modelos de issues e pull requests, com evidências de teste e revisão do auxílio de IA.
- Exclusões de dados locais, memórias, segredos comuns, bytecode e exercício externo.
- Caminhos pessoais substituídos por referências genéricas em dois documentos históricos, preservando as decisões registradas.

O pacote de fontes preparado em `work/publicacao/` é uma fotografia dos arquivos atuais, incluindo o desenvolvimento local preexistente. Exclui o histórico Git, os logs privados, o exercício Frota externo, o modelo e os binários. O histórico original continua preservado no repositório local. A proposta é iniciar o repositório público com essa fotografia revisada; publicar o histórico antigo exigiria uma revisão própria.

## Verificações de publicação

A auditoria local usa a lista de arquivos existentes fornecida por `git ls-files --cached --others --exclude-standard`, elimina duplicatas e verifica links Markdown locais, arquivos grandes/binários e padrões comuns de tokens/chaves e caminhos pessoais. O manifesto local em `work/publicacao/auditoria.json` registra os hashes dos arquivos selecionados.

Essa busca é heurística e não certifica ausência de segredos. O histórico antigo não integra o pacote. O `.gitignore` não remove arquivos já versionados nem substitui revisão humana.

## Verificação funcional nesta preparação

A primeira tentativa de suíte no Windows foi interrompida: os atalhos `java` e `javac` da Oracle no PATH excederam oito segundos até em `-version`. Os executáveis diretos de `C:/Program Files/Java/jdk-27/bin` responderam com Java/javac 27. A repetição usa esse diretório no início do PATH apenas na sessão e TEMP/TMP em `work/publicacao-temp`, sem instalação ou mudança permanente do Windows.

Comandos da repetição, na raiz, em PowerShell:

```powershell
$env:PATH='C:/Program Files/Java/jdk-27/bin;'+$env:PATH
$env:TEMP=(Resolve-Path work/publicacao-temp).Path
$env:TMP=$env:TEMP
$env:PYTHONPATH=(Resolve-Path src).Path
python -m unittest discover -s tests -v
git diff --check
```

O diretório do JDK é específico deste ambiente; em outro computador use um JDK disponível.

Resultado da execução completa em 2026-11-03, Windows, Python 3.14 e JDK 27: **227 testes executados em 105,215 s; 225 aprovados, zero falhas/erros e dois pulos de plataforma** (instalador Linux real e criação de symlink sem privilégio no Windows). `git diff --check` passou. As tentativas interrompidas anteriores não foram contadas como aprovação. O log completo fica localmente em `work/publicacao-testes-final.log` e não acompanha a publicação.

Nenhum build de bundle, download, instalação ou aceitação Linux/WSL foi realizado nesta preparação documental. Os registros antigos em `tests/acceptance/checklist.md` continuam sendo evidências históricas, com suas próprias datas e hashes.

## Antes de publicar

- Conferir os arquivos e o resultado dos testes desta preparação.
- Confirmação separada para commit e publicação recebida nesta preparação, após a apresentação do destino e das exclusões.
- Criar o repositório público no perfil correto, sem licença até nova decisão.
- Publicar somente a fotografia revisada, preservando o repositório local original.
- Confirmar a página pública e os arquivos enviados antes de declarar a publicação concluída.

Condições de contribuição e redistribuição permanecem pendentes enquanto a licença não for escolhida. Este preparo não configura colaboradores com acesso de escrita nem altera permissões da conta.
