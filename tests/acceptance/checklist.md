# Aceitação Linux Mint — registro

Status atual: **APROVADO NO UBUNTU 24.04 VIA WSL, INCLUINDO `run-offline.sh` COMPLETO NO BUNDLE DE 23/10. Validação no Linux Mint e em USB 2.0 real ainda pendente.**

Em 2026-10-23 o bundle foi reconstruído duas vezes (a última após as correções da auditoria: 1.929.787.220 bytes) e `sha256sum -c manifest.sha256` passou nas duas versões. Em 2026-10-24 o `run-offline.sh` completo passou no WSL com esse bundle: instalação, perfil padrão criado, edição de `repair_attempts` preservada após reinstalar, abertura na pasta atual, abertura após remover a origem e ausência de `.class` na entrega — **PASS em 74 s**. As tentativas anteriores nesse mesmo dia falharam por espaço no host, não pelo artefato: o `C:` estava com 1,8 GB livres, o VHD do WSL é dinâmico e o ext4 entrava em `emergency_ro` durante a escrita de ~5 GB. Após limpar caches do guest e dados de teste, o host passou a 40,5 GB livres e o teste passou. Libere espaço no `C:` antes de repetir.

Na mesma data, a suíte completa rodou dentro do Linux/WSL com os binários do bundle (JDK 17 e tesseract 5.5.3): **168 testes, 0 falhas, 0 skips**. Os dois testes que pulam no Windows passaram — instalador real (`test_install_and_update_preserve_criteria_and_state`) e symlink de escape (`test_rejects_symlink_that_escapes_root`). O caminho de OCR real também foi exercitado: PDF só-imagem gerado com `pdftoppm`/`tiff2pdf` do bundle, `PdfExtractor` retornou `source=ocr` e recuperou os nomes do UML.

Preencha no mesmo modelo de computador que será usado na competição. Um item só pode virar `PASS` com comando/medição anexado.

| Verificação | Estado | Evidência |
|---|---|---|
| Bundle possui 4 artefatos e até 2 GB | PASS WSL | 4 arquivos; 1.929.787.220 bytes (bundle de 2026-10-23, pós-correções) |
| `sha256sum -c manifest.sha256` | PASS WSL | bundle de 2026-10-23: `runtime.tar.gz: OK`; `model.gguf: OK` |
| `./instalar.sh` sem download e sem `sudo` | PASS WSL 2026-10-23 | `run-offline.sh` completo com o bundle final; `sha256sum -c` OK e instalação só com arquivos locais |
| Abre na pasta atual e após a origem ficar indisponível | PASS WSL 2026-10-23 | `run-offline.sh`: abriu em `Projeto com acento á` e abriu de novo após `mv origem origem-removida` |
| Instalação + primeiro prompt em até 5 minutos | PASS WSL 2026-10-23 / USB real pendente | `PASS: inicialização offline após remover a origem em 74 s` (duas aberturas) |
| Pico de RAM cabe em 4 GB | PASS WSL 2026-10-24 / hardware real pendente | bundle final: pico somado `llama-server` + `python3` = 2.533.184 KiB (~2,42 GiB), 0 swaps |
| Modelo responde a texto comum | PASS WSL 2026-10-24 | bundle final instalado; pergunta em português respondida corretamente sobre classe em Java |
| `/pdf` funciona com caminho contendo espaços e acentos | PASS WSL 2026-10-24 | app instalado em `.../Projeto com acento á` com `Enunciado da prova á.pdf`: `/pdf` → `1` respondeu `PDF carregado. Classes reconhecidas: Veiculo, Carro` |
| PDF textual e PDF imagem/OCR geram evidência ou incerteza explícita | PASS WSL 2026-10-24 / OCR no Linux Mint pendente | PDF só-imagem gerado com ferramentas do bundle: `PdfExtractor` real retornou `source=ocr` e recuperou `class Veiculo`, `- placa: String`, `class Carro`, `Veiculo herda de Carro` |
| UML ambíguo bloqueia geração até confirmação | PASS automatizado | suíte de integração |
| Gera e compila com `--release 8` | PASS WSL 2026-10-24 | `test_compiles_with_java_8_target_and_runs_formula ... ok` com o JDK do bundle no Linux; geração+execução real do Frota em 22/10 |
| Programa Java em loop é encerrado no timeout | PASS automatizado | suíte do toolchain |
| `/desfazer` preserva edição posterior do usuário | PASS automatizado | suíte de workspace/histórico |
| Symlink de escape é recusado no Linux | PASS WSL 2026-10-24 | suíte completa no Linux: `test_rejects_symlink_that_escapes_root ... ok` |
| Nenhuma conexão além de `127.0.0.1` | PASS WSL 2026-10-24 | `ss`: `llama-server` escutando só em `127.0.0.1:55423`; única conexão estabelecida é `python3` ↔ `llama-server` no loopback |
| Reinstalação preserva critérios e memória | PASS WSL 2026-10-24 | `test_install_and_update_preserve_criteria_and_state ... ok` na suíte completa em Linux (instalador real) |
| Perfil padrão instalado e preservado na reinstalação | PASS WSL 2026-10-23 | `run-offline.sh` completo: perfil criado, `repair_attempts` editado para 1 e mantido após reinstalar (`JAVA_ASSISTANT_NO_START=1`) |
| `/perfil` mostra origem, limites e comandos ativos | PASS WSL 2026-10-24 | app instalado: `perfil global: .../perfil.json`, `origem: global`, `limites: contexto 4096 tokens, saída 640, reparos 2, arquivos 40` |
| Nenhum `.class`/teste fica na pasta de entrega | PASS WSL 2026-10-23 | `run-offline.sh` completo no bundle final: `find . -name '*.class'` na pasta do projeto não achou nada |

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
- RAM: pico somado `llama-server` + `python3` = 2.533.184 KiB (~2,42 GiB) em 24/10 com o bundle final
- Tipo/velocidade da mídia: SSD local; USB 2.0 pendente
- SHA-256 de `runtime.tar.gz`: `876e0aa63c8abb81a67dc8618a278033b538f13b13eb10065dd07ba9a8373a7f`
- SHA-256 de `model.gguf`: `fc3937db7dda9d9ef68ce1f63b5a84ac850ec3c07578461d645e5a88509348e3`
- Data: 2026-10-24 (bundle de 2026-10-23)
- Resultado final: `run-offline.sh` completo PASS WSL; PASS final no Linux Mint/hardware real pendente

## Validação de 2026-10-28 — pacote após os experimentos

Este registro complementa o histórico acima. Linux Mint físico e USB 2.0 foram explicitamente adiados pelo usuário; não receberam PASS.

- Fonte atual: proteção do melhor candidato, revalidação e relatório coerente após restauro; contrato/pedido preservados no contexto. Geração experimental por corpos de membros removida por falha de compilação nos três exercícios. Ampliação para dez reparos descartada por ausência de ganho nos controles fixo e com amostragem normal; padrão 2 e faixa 0–5 mantidos.
- Suíte completa Windows: 217 testes, zero falhas, dois pulos de plataforma, 129,932 s. TEMP/TMP apontados para `work/audit-temp` devido à restrição do temporário do sistema.
- Suíte completa Ubuntu 24.04/WSL com as ferramentas nativas já existentes: 217 testes, zero falhas e zero pulos, 97,806 s.
- Bundle: `work/experiments-2026-10-27/bundle-current`, 1.929.798.693 bytes, abaixo do limite de 2.147.483.648 bytes. Auditoria confirmou 38 fontes idênticos aos testados, ausência do componente rejeitado, ferramentas Java/PDF/OCR e dados de idiomas presentes.
- SHA-256 de `runtime.tar.gz`: `a1b0c9fba21b682b83f3f1b83bbe0caf808ae978c62b66e0150d4c5ebbf41a67`.
- SHA-256 de `model.gguf`: `fc3937db7dda9d9ef68ce1f63b5a84ac850ec3c07578461d645e5a88509348e3`.
- Aceitação do bundle atual: `run-offline.sh` completo, exit 0, **PASS em 73 s** para instalação/aberturas após remover a origem. Tempo total do runner, incluindo a cópia isolada do pacote: 116,648 s. Perfil editado preservado após reinstalação, pasta com espaços/acentos correta e ausência de `.class` na entrega conferidos pelo script.
- Geração real: variante de contexto com cinco reparos fez 10/17 no Frota; ReservaSala 9/9 e Bilhete 7/7. Esses resultados não equivalem ao juiz oficial nem comprovam solução geral de qualquer PDF. A confirmação normal com dez reparos fez 9/17, igual ao controle pareado de cinco reparos.
- Evidências completas e comandos: `work/experiments-2026-10-27/{results.md,decisions.md,commands.md,acceptance-current.log,bundle-audit.json}`. A primeira confirmação normal foi interrompida pelo reinício do WSL e não foi contada como resultado de qualidade; uma execução nova completa foi usada na decisão.
