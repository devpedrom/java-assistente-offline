# Artefatos Linux necessários para gerar o bundle

> Para quem clonou o repositório público: os artefatos abaixo não acompanham o
> código. Os registros de preparação e validação desta máquina são históricos;
> não indicam que os arquivos existem no seu clone. Prepare-os separadamente,
> com autorização, conferindo origem, integridade e termos de redistribuição.

O diretório `artifacts/linux-x86_64` não entra no Git. Antes de executar `packaging/linux/build-bundle.sh`, ele deve ter esta estrutura:

```text
artifacts/linux-x86_64/
  model.gguf
  llama/
    llama-server
    libggml*.so e demais bibliotecas do mesmo release
  native.tar.gz
    # arquivo compactado cuja raiz contém bin/, lib/ e share/
    # preserva os links simbólicos dos binários Linux
```

## Modelo fixado

- Repositório oficial: `Qwen/Qwen2.5-Coder-3B-Instruct-GGUF`
- Arquivo: `qwen2.5-coder-3b-instruct-q3_k_m.gguf`
- Nome dentro do projeto: `model.gguf`
- Tamanho publicado: aproximadamente 1,72 GB.
- Baixado e verificado neste projeto: 1.724.178.880 bytes, assinatura `GGUF`.
- SHA-256 verificado contra o arquivo oficial: `fc3937db7dda9d9ef68ce1f63b5a84ac850ec3c07578461d645e5a88509348e3`.
- Motivo da troca: o modelo 1.5B não foi consistente no exercício de aceitação; o 3B Q3_K_M passou na geração guiada e ainda mantém o bundle abaixo do limite rígido de 2 GB.

## llama.cpp fixado

- Release oficial: `b11797`, CPU Ubuntu x64.
- `llama-server` verificado como ELF x86-64.
- SHA-256 do executável: `5eb6defebd2de4a6c4c07b85f37ba82abb70d839e265f3b34f23bc0c9c215bba`.
- As bibliotecas versionadas foram mantidas junto do servidor; os nomes que eram links simbólicos no `.tar.gz` foram materializados como cópias regulares porque este Windows não permite criar symlinks.

## Regras para os binários

- Use o release CPU Ubuntu x64 do `ggml-org/llama.cpp`, mantendo `llama-server` e suas bibliotecas `.so` juntos em `llama/`.
- O arquivo unificado `native.tar.gz` deve conter OpenJDK 17 (incluindo `javac` e `javap`), Poppler e Tesseract para Linux x86-64, com as bibliotecas dinâmicas em `lib`.
- O arquivo deve conter `lib/libgomp.so.1`, exigido pelo `llama-server`, e `share/tessdata/eng.traineddata`, `por.traineddata` e `osd.traineddata`.
- Não misture binários Windows no diretório Linux.
- Registre SHA-256 e versões em `tests/acceptance/checklist.md`.

## Perfil no bundle

- `packaging/linux/perfil-padrao.json` é obrigatório: `assemble_runtime.py` recusa o build se ele faltar e o empacota como `share/perfil-padrao.json` dentro de `runtime.tar.gz`.
- `instalar.sh` copia o perfil para `$XDG_CONFIG_HOME/java-assistente/perfil.json` somente se o arquivo ainda não existir, então reinstalar preserva o perfil editado.
- O perfil padrão usa caminhos relativos (`tools/native/bin/javac`, etc.) resolvidos a partir de `JAVA_ASSISTANT_HOME`; não coloque caminho absoluto da máquina de build.

O build recusa artefatos ausentes e bundles acima de 2 GB. A aprovação final exige rodar `tests/acceptance/run-offline.sh` no Linux Mint real.

## Estado desta máquina

`model.gguf`, `llama/` e `native.tar.gz` estão prontos em `artifacts/linux-x86_64`. A execução ponta a ponta foi validada no Ubuntu 24.04 via WSL; ainda é recomendável repetir a aceitação no Linux Mint e no hardware real da competição.
