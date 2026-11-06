# Aceitação Linux Mint — registro

Status atual (2026-11-06): **165 testes e 5/5 contratos aprovados no WSL; novo pacote aceito em dois processos. Bateria real E5 reprovada em 14/17. Linux Mint e USB 2.0 real não verificados.**

Preencha no mesmo modelo de computador que será usado na competição. Um item só pode virar `PASS` com comando/medição anexado.

Tabela histórica de aprovação inicial (as medições atuais estão no complemento de 2026-11-06 ao final):

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

## Regressão de 2026-11-04 — branch de fidelidade

- Windows: `$env:PYTHONPATH=(Resolve-Path src).Path; python -m unittest discover -s tests -v`
  → 126 testes, 122 aprovados, 4 pulados (dois symlinks, instalador Linux e script do validador), após todas as correções.
- WSL com `tools/native/bin` do runtime no PATH:
  `PYTHONPATH=src python3 -m unittest discover -s tests -v` → 125/125 aprovados após as oito correções da revisão, antes da última proteção de encerramento do CLI. Essa proteção tem regressão RED→GREEN no Windows; não se declara uma suíte WSL de 126 testes executada.
- A primeira tentativa WSL, sem esse PATH, falhou (7 falhas, 13 erros) por
  `javac` ausente. Não foi considerada aprovação; nenhum pacote foi instalado.
- `PYTHONPATH=src python3 -m unittest tests.packaging.test_installer -v` → 3/3 aprovados no WSL.
- Build com os artefatos existentes, usando `OUTPUT_DIR` de teste separado:
  `bash packaging/linux/build-bundle.sh` → 1.929.782.644 bytes inicialmente. O pacote final, com runtime atualizado por `assemble_runtime.py` e manifesto recalculado, tem 1.929.784.003 bytes, abaixo de 2 GiB.
- A extração inicial do runtime pelo filesystem Windows excedeu 120 s;
  foi repetida em temporário nativo do WSL. O timeout não conta como aprovação.
  A limpeza dessa extração parcial encontrou um header somente leitura
  (`WinError 5`); o restante do temporário foi preservado. O primeiro bundle
  de teste foi removido; o bundle final permanece disponível.
- `.assistente` agora possui UUID persistente, JSON/JSONL canônicos e SQLite
  reconstruível; testes cobrem interrupção, movimento de pasta, edição externa,
  troca de PDF/critérios e confinamento por symlink.
- Primeira aceitação em dois processos: aprovada em 35 s. Aceitação do pacote
  final: **aprovada em 40 s**, com hashes corretos, origem removida e contrato
  retomado na segunda sessão sem reenviar o enunciado.
- Houve reinícios do servidor e um timeout de 600 s na extração temporária
  anterior à última suíte WSL planejada. Essa tentativa não iniciou a suíte e
  não conta como aprovação; a aceitação final foi executada separadamente.
- Fidelidade: 4/5 contratos; nenhuma classe E5 reconhecida. Ver `qualidade.md`.
- Não comprovados: geração real com o modelo nesta versão, bateria real E5,
  limite de RAM/CPU/USB e gate final em Linux Mint 4–6 GB.
- Tentativa real E1: runtime e enunciado carregaram, mas a execução terminou
  durante a geração sem solução concluída. Não foi considerada aprovação.

### Revisão independente

Foram reproduzidas e corrigidas oito falhas, cada uma com regressão que falhou
antes da correção: seleção de overload boxed; rejeição indevida de composição
por `super`; escolha de classe por prefixo; evidência antiga após atualização
interrompida de requisitos; relatório após desfazer; escopo de compilação
parcial; troca de PDF durante sessão aberta; recuperação do código anterior
após reiniciar. A suíte completa acima foi executada depois dessas correções.
Uma regressão adicional garante que o runtime pare mesmo se o checkpoint final
falhar; após ela, a suíte Windows completa passou com 126 testes.
Não houve commit nem substituição do pacote anterior em `dist/`.

## Verificação final — 2026-11-06, correção por método

Ambiente: Ubuntu 24.04 via WSL, ferramentas nativas extraídas do runtime
existente, sem download ou instalação de dependências. Não é evidência de
Linux Mint nem de hardware CPU-only com 4–6 GB.

| Comando executado | Resultado |
|---|---|
| `PYTHONPATH=src python3 -m unittest discover -s tests -v` | 165 aprovados, 0 falhas/erros, 0 pulados; 165,592 s |
| `PYTHONPATH=src python3 tests/qualidade/medir.py` | 5/5 contratos completos; comportamento não medido nessa chamada |
| `PYTHONPATH=src python3 -m unittest tests.packaging.test_installer -v` | 3 aprovados, 0 falhas/erros/pulados; 0,093 s |
| `OUTPUT_DIR="$PWD/dist/java-assistente-metodos-linux-x86_64" bash packaging/linux/build-bundle.sh` | pacote criado, 4 arquivos, 1.929.791.610 bytes, abaixo de 2 GiB |
| `tar -tzf dist/java-assistente-metodos-linux-x86_64/runtime.tar.gz` | auxiliar `app/java_assistant/java/MethodBodies.java` incluído |
| `bash tests/acceptance/run-offline.sh dist/java-assistente-metodos-linux-x86_64` | PASS, 32 s; origem removida antes da segunda abertura, contrato retomado |
| `sha256sum -c manifest.sha256` dentro do novo pacote | runtime e modelo OK |
| `git diff --check` | aprovado |

- Novo runtime SHA-256: `6411449565c42898ae7db7a787268d9341808221159a440b5d6abb6599abd5a4`.
- Modelo SHA-256: `fc3937db7dda9d9ef68ce1f63b5a84ac850ec3c07578461d645e5a88509348e3`.
- O pacote anterior em `dist/java-assistente-linux-x86_64` foi preservado.
- A bateria fornecida executada pelo driver real continua **14/17, exit 1**:
  Hatch automático 405 em vez de 450; volume com quatro/cinco passageiros
  zero em vez de 300. O modelo respondeu no formato de corpos, mas repetiu
  a implementação anterior. Os seis hashes de fonte ficaram iguais; não houve
  correção manual. Portanto **a meta de aprovação do desafio não foi atingida**.
- A primeira suíte Windows desta etapa teve 156 executados: 149 aprovados,
  6 pulados e 1 erro em `test_undo_survives_restart_and_invalidates_report_evidence`
  (modelo roteirizado ainda retornava classe inteira). O fixture foi atualizado
  para corpos e o teste passou; essa primeira execução não conta como aprovação.
- Houve uma tentativa diagnóstica WSL sem o PATH nativo que falhou por
  `pdftotext` ausente; a extração foi repetida com os binários empacotados.
  Nenhuma dependência foi instalada e nenhum timeout foi contado como PASS.
- A régua adicional detectou e permitiu reproduzir uma regressão E4 após a
  primeira suíte verde: um nome de classe quebrado pelo OCR contaminava a
  classe anterior. A correção tem teste RED→GREEN; a suíte final e os 5 contratos
  acima foram executados depois dela e dos últimos ajustes de protocolo.
- Logs: `.superpowers/sdd/2026-11-06-correcao-por-metodo/` (`full-suite-wsl.log`,
  `contracts-wsl.log`, `packaging-tests.log`, `build.log`, `acceptance.log`,
  `diagnostic-mode-retest.log`, comparações de hashes e ledger).
- Ainda não verificados: Linux Mint real, RAM/CPU/instruções e cópia por USB no
  hardware-alvo, inspeção efetiva de tráfego, testes secretos dos jurados.
- Nenhum commit, push, instalação persistente ou troca de modelo foi realizado.
