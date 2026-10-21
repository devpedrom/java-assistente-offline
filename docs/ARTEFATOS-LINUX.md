# Artefatos Linux necessários para gerar o bundle

O diretório `artifacts/linux-x86_64` não entra no Git. Antes de executar `packaging/linux/build-bundle.sh`, ele deve ter esta estrutura:

```text
artifacts/linux-x86_64/
  model.gguf
  llama/
    llama-server
    libggml*.so e demais bibliotecas do mesmo release
  jdk/
    bin/java
    bin/javac
    bin/javap
  poppler/
    bin/pdftotext
    bin/pdftoppm
    lib/...
  tesseract/
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

## Regras para os binários

- Use o release CPU Ubuntu x64 do `ggml-org/llama.cpp`, mantendo `llama-server` e suas bibliotecas `.so` juntos em `llama/`.
- Use um JDK/JRE 17 x64 que contenha também `javac` e `javap`; somente um JRE não basta.
- Prepare Poppler e Tesseract em um Linux Mint da mesma geração do computador-alvo e copie também as bibliotecas dinâmicas necessárias.
- Não misture binários Windows no diretório Linux.
- Registre SHA-256 e versões em `tests/acceptance/checklist.md`.

O build recusa artefatos ausentes e bundles acima de 2 GB. A aprovação final exige rodar `tests/acceptance/run-offline.sh` no Linux Mint real.
