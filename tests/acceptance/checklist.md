# Aceitação Linux Mint — registro

Status atual: **PENDENTE — este projeto foi desenvolvido em Windows sem WSL, Docker ou Podman.**

Preencha no mesmo modelo de computador que será usado na competição. Um item só pode virar `PASS` com comando/medição anexado.

| Verificação | Estado | Evidência |
|---|---|---|
| Bundle possui 4 artefatos e até 2 GB | PENDENTE | — |
| `sha256sum -c manifest.sha256` | PENDENTE | — |
| `./instalar.sh` sem rede e sem `sudo` | PENDENTE | — |
| Abre após a pasta de origem ficar indisponível | PENDENTE | — |
| Instalação + primeiro prompt em até 5 minutos (USB 2.0) | PENDENTE | — |
| Pico de RAM cabe em 4 GB | PENDENTE | — |
| Modelo responde a texto comum | PENDENTE | — |
| `/pdf` funciona com caminho contendo espaços e acentos | PENDENTE | — |
| PDF textual e PDF imagem/OCR geram evidência ou incerteza explícita | PENDENTE | — |
| UML ambíguo bloqueia geração até confirmação | PENDENTE | — |
| Gera e compila com `--release 8` | PENDENTE | — |
| Programa Java em loop é encerrado no timeout | PENDENTE | — |
| `/desfazer` preserva edição posterior do usuário | PENDENTE | — |
| Symlink de escape é recusado no Linux | PENDENTE | — |
| Nenhuma conexão além de `127.0.0.1` | PENDENTE | — |
| Reinstalação preserva critérios e memória | PENDENTE | — |
| Nenhum `.class`/teste fica na pasta de entrega | PENDENTE | — |

## Comandos mínimos

```sh
sha256sum -c manifest.sha256
du -sh .
/usr/bin/time -v tests/acceptance/run-offline.sh /caminho/do/bundle
ss -lntp
```

## Identificação da aprovação

- Linux Mint/versão:
- CPU:
- RAM:
- Tipo/velocidade da mídia:
- SHA-256 de `runtime.tar.gz`:
- SHA-256 de `model.gguf`:
- Data:
- Resultado final: PENDENTE
