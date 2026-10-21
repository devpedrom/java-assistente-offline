# Artefatos Linux necessários para gerar o bundle

O diretório `artifacts/linux-x86_64` não entra no Git. Antes de executar `packaging/linux/build-bundle.sh`, ele deve ter esta estrutura:

```text
artifacts/linux-x86_64/
  model.gguf
  llama/
    llama-server
    libggml*.so e demais bibliotecas do mesmo release
  native/
    bin/java
    bin/javac
    bin/javap
    bin/pdftotext
    bin/pdftoppm
    bin/tesseract
    lib/...
    share/tessdata/eng.traineddata
    share/tessdata/por.traineddata
```

## Modelo fixado

- Repositório oficial: `Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF`
- Arquivo: `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`
- Nome dentro do projeto: `model.gguf`
- Tamanho publicado: aproximadamente 1,12 GB.
- Baixado e verificado neste projeto: 1.117.320.768 bytes, assinatura `GGUF`.
- SHA-256 verificado contra o `X-Linked-ETag` oficial: `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`.

## llama.cpp fixado

- Release oficial: `b11797`, CPU Ubuntu x64.
- `llama-server` verificado como ELF x86-64.
- SHA-256 do executável: `5eb6defebd2de4a6c4c07b85f37ba82abb70d839e265f3b34f23bc0c9c215bba`.
- As bibliotecas versionadas foram mantidas junto do servidor; os nomes que eram links simbólicos no `.tar.gz` foram materializados como cópias regulares porque este Windows não permite criar symlinks.

## Regras para os binários

- Use o release CPU Ubuntu x64 do `ggml-org/llama.cpp`, mantendo `llama-server` e suas bibliotecas `.so` juntos em `llama/`.
- O diretório unificado `native/` deve conter OpenJDK 17 (incluindo `javac` e `javap`), Poppler e Tesseract para Linux x86-64, com as bibliotecas dinâmicas em `native/lib`.
- Não misture binários Windows no diretório Linux.
- Registre SHA-256 e versões em `tests/acceptance/checklist.md`.

O build recusa artefatos ausentes e bundles acima de 2 GB. A aprovação final exige rodar `tests/acceptance/run-offline.sh` no Linux Mint real.

## Estado desta máquina

`model.gguf` e `llama/` estão prontos em `artifacts/linux-x86_64`. O diretório `native/` continua pendente: a tentativa cruzada com pacotes Linux falhou porque o Windows atual bloqueia os links simbólicos exigidos. Gere `native/` em Linux/WSL ou habilite um ambiente que preserve symlinks antes de chamar o bundle final de pronto.
