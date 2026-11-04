# Aceitação Linux Mint — registro

Status atual: **APROVADO NO UBUNTU 24.04 VIA WSL; validação no Linux Mint e em USB 2.0 real ainda pendente.**

Preencha no mesmo modelo de computador que será usado na competição. Um item só pode virar `PASS` com comando/medição anexado.

| Verificação | Estado | Evidência |
|---|---|---|
| Bundle possui 4 artefatos e até 2 GB | PASS WSL | 4 arquivos; 1.929.769.984 bytes |
| `sha256sum -c manifest.sha256` | PASS WSL | `runtime.tar.gz: OK`; `model.gguf: OK` |
| `./instalar.sh` sem download e sem `sudo` | PASS WSL | instalação concluída somente com o bundle local |
| Abre na pasta atual e após a origem ficar indisponível | PASS WSL | abriu automaticamente em `Projeto com acento á`; origem renomeada antes da segunda abertura |
| Instalação + primeiro prompt em até 5 minutos | PASS WSL / USB real pendente | 22 s no ambiente temporário; 42,09 s incluindo duas aberturas e limpeza do teste |
| Pico de RAM cabe em 4 GB | PASS WSL / hardware real pendente | máximo de 2.414.300 KiB; 0 swaps |
| Modelo responde a texto comum | PASS WSL | geração real do exercício Frota com Qwen2.5-Coder-3B Q3_K_M |
| `/pdf` funciona com caminho contendo espaços e acentos | PASS automatizado / pacote real pendente | integração aprovada; instalação abriu em `Projeto com acento á` |
| PDF textual e PDF imagem/OCR geram evidência ou incerteza explícita | PARCIAL | PDF textual real aprovado; OCR real no Linux Mint pendente |
| UML ambíguo bloqueia geração até confirmação | PASS automatizado | suíte de integração |
| Gera e compila com `--release 8` | PASS WSL | Frota gerada, contrato validado, compilada e executada |
| Programa Java em loop é encerrado no timeout | PASS automatizado | suíte do toolchain |
| `/desfazer` preserva edição posterior do usuário | PASS automatizado | suíte de workspace/histórico |
| Symlink de escape é recusado no Linux | PENDENTE Linux Mint | — |
| Nenhuma conexão além de `127.0.0.1` | PASS configuração / inspeção real pendente | servidor iniciado com `--host 127.0.0.1` |
| Reinstalação preserva critérios e memória | PASS automatizado | suíte do instalador |
| Nenhum `.class`/teste fica na pasta de entrega | PASS WSL | `run-offline.sh` aprovado |

## Comandos mínimos

```sh
sha256sum -c manifest.sha256
du -sh .
/usr/bin/time -v tests/acceptance/run-offline.sh /caminho/do/bundle
ss -lntp
```

## Identificação da aprovação

- Linux Mint/versão: pendente; validação atual em Ubuntu 24.04 via WSL
- CPU: processador do computador de desenvolvimento, 2 threads configuradas para o modelo
- RAM: pico do processo de aceitação 2.414.300 KiB
- Tipo/velocidade da mídia: SSD local; USB 2.0 pendente
- SHA-256 de `runtime.tar.gz`:
- SHA-256 de `model.gguf`:
- Data: 2026-10-22
- Resultado final: PASS WSL; PASS final no Linux Mint/hardware real pendente
