# Arquitetura atual: mapa de leitura

Este mapa ajuda a encontrar o código. A implementação e os testes são a fonte do comportamento atual. A [especificação principal](superpowers/specs/2026-10-21-assistente-java-offline-design.md) também contém objetivos ainda não implementados; consulte as limitações no [estado do projeto](ESTADO-DO-PROJETO.md).

## Caminho principal

`cli.py` carrega configuração e perfil, inicia o runtime local e cria `AssistantSession`. A sessão recebe comandos e pedidos, seleciona o PDF e coordena extração, contrato, geração, reparos e relatório. O modelo responde pelo cliente local; escrita, compilação e execução passam pelas ferramentas controladas.

| Área | Arquivos ou diretório | Responsabilidade |
| --- | --- | --- |
| Entrada e configuração | `cli.py`, `config.py`, `profile.py` | CLI, diretórios XDG, perfil e limites |
| Coordenação | `session.py` | Fluxo conversacional, geração e verificadores locais |
| Contratos e planejamento | `core/spec.py`, `core/solver.py`, `core/facts.py`, `core/budget.py` | Estrutura, confiança, regras textuais, ordem e contexto |
| Adaptadores | `adapters/` | Interfaces de linguagem e implementação Java 8; stub de teste não implica suporte a outra linguagem |
| PDF e UML | `pdf/`, `uml/extract.py` | Descoberta, extração/OCR e interpretação textual |
| Modelo local | `model/` | Runtime llama.cpp, transporte HTTP local, protocolo de ações e validação |
| Java | `java/` | Compilação, inspeção de classes, execução e validação estrutural |
| Arquivos e histórico | `workspace/` | Limite de escrita e desfazer preservando edição posterior |
| Memória existente | `memory/store.py` | Registro SQLite por escopo de PDF/projeto |
| Evidências | `review/report.py` | Separação entre confirmação, inferência, compilação, teste e pendência |
| Distribuição | `packaging/linux/` | Montagem do runtime e instalador offline |

Os caminhos da tabela são relativos a `src/java_assistant/`, exceto distribuição.

## Fronteiras que devem permanecer explícitas

O diretório de trabalho é a raiz imutável do exercício e o limite de escrita. Caminhos absolutos, travessia por `..` e escapes por symlink devem ser rejeitados. O modelo não executa shell; o controlador valida ações e limita processos.

O endpoint HTTP do modelo é local. Uso offline não significa ausência de comunicação entre processos em loopback. Não introduza APIs remotas, telemetria ou downloads durante instalação e execução.

O contrato distingue evidência confirmada e inferência. A interpretação textual não equivale à leitura visual completa do UML. Assinaturas de classes locais e verificadores possuem regras específicas no [manual](USO-RAPIDO.md); não os trate como avaliador oficial.

O armazenamento atual de eventos não comprova a entrega da memória portátil `.assistente` planejada. Para mexer nessa área, leia o [design de memória](superpowers/specs/2026-10-22-memoria-portatil-entre-sessoes-design.md) e o [plano](superpowers/plans/2026-10-22-memoria-portatil-entre-sessoes.md).

## Onde verificar mudanças

- `tests/unit/`: regras isoladas de contrato, orçamento, perfil, modelo e workspace.
- `tests/integration/`: fluxo de sessão, solver, PDF/UML, classes locais e ferramentas Java.
- `tests/fixtures/enunciados/`: cenários sintéticos com contratos, respostas simuladas e casos de execução.
- `tests/packaging/`: comportamento do instalador e runtime.
- `tests/acceptance/`: bundle completo e registro de plataforma/hardware.

Os cenários com respostas simuladas verificam o controlador e não medem a qualidade de inferência do modelo real. Uma alteração em `session.py` pode afetar vários desses grupos; procure também os chamadores antes de editar.
