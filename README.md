# Assistente Java POO Offline

Assistente de terminal para resolver e revisar exercícios de Java orientado a objetos a partir de um PDF, com inferência local, compilação para Java 8 e verificações limitadas por tempo. O sistema alvo é Linux Mint x86-64, somente CPU, com 4–6 GB de RAM.

**Projeto em desenvolvimento.** O código Python está neste repositório; modelo, JDK e ferramentas nativas são preparados separadamente no bundle. Clonar o código não instala um assistente pronto para uso.

## Comece aqui

| Objetivo | Documento |
| --- | --- |
| Usar o pacote offline | [Uso rápido](docs/USO-RAPIDO.md) |
| Preparar o bundle Linux | [Artefatos necessários](docs/ARTEFATOS-LINUX.md) |
| Contribuir com código ou documentação | [Guia de contribuição](CONTRIBUTING.md) |
| Começar com uma IA | [Contexto e prompt inicial](docs/CONTEXTO-PARA-IA.md) e [AGENTS.md](AGENTS.md) |
| Entender módulos e decisões | [Arquitetura atual](docs/ARQUITETURA.md) |
| Consultar limitações e próximos passos | [Estado do projeto](docs/ESTADO-DO-PROJETO.md) |
| Configurar limites e ferramentas | [Perfil de competição](docs/PERFIL-COMPETICAO.md) |

## O que o assistente faz

- Seleciona um PDF da pasta atual com `/pdf` e extrai texto, recorrendo a OCR nas condições descritas no manual.
- Deriva um contrato de classes, membros e relações a partir da notação textual reconhecida.
- Gera e corrige fontes usando `llama.cpp` e um modelo GGUF local.
- Compila com alvo Java 8 e executa verificadores locais com limites.
- Restringe escrita à pasta do exercício, mantém histórico para desfazer e apresenta evidências em `/relatorio`.
- Usa perfis declarativos para caminhos, limites e comandos.

O UML visual completo (caixas, setas e posições) ainda não é interpretado. Compilar não comprova regras de negócio; verificadores locais não equivalem ao juiz oficial. A memória portátil entre sessões tem design e plano próprios e não deve ser anunciada como concluída.

## Desenvolver e testar

Requisito do código: Python 3.10 ou superior. O manifesto não declara dependências Python de execução. Testes com ferramentas reais dependem de Java e, conforme o cenário, ferramentas PDF/OCR; consulte os pulos e resultados efetivos da suíte. Não é necessário baixar o modelo para testar os caminhos que usam respostas simuladas.

Linux, na raiz do clone:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

PowerShell, na raiz do clone:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
python -m unittest discover -s tests -v
```

Esses comandos testam o código; não montam nem instalam o bundle. Para executar o produto completo, siga o [manual](docs/USO-RAPIDO.md). O entry point requer uma instalação com `JAVA_ASSISTANT_HOME`, modelo e ferramentas presentes.

## Distribuição offline

Após preparar os artefatos locais, no Linux:

```bash
bash packaging/linux/build-bundle.sh
bash tests/acceptance/run-offline.sh dist/java-assistente-linux-x86_64
```

O bundle inclui instalador, runtime, ferramentas e modelo, com limite rígido de 2 GiB. A instalação e o uso no equipamento alvo devem funcionar sem internet, API ou `sudo`, inclusive após remover o pendrive. Preparar o ambiente de desenvolvimento e colaborar pelo GitHub são atividades separadas do uso offline.

Os registros de aceitação em [tests/acceptance/checklist.md](tests/acceptance/checklist.md) identificam datas, versões e evidências em WSL. Eles não certificam automaticamente o código atual nem o Linux Mint físico. Medições no hardware alvo e em USB real permanecem pendentes.

## Estrutura

```text
src/java_assistant/   Controlador, contratos, modelo local e verificadores
packaging/linux/     Montagem e instalação do bundle offline
instructions/        Critérios editáveis usados na geração
tests/               Testes unitários, integração, fixtures e aceitação
docs/                Operação, arquitetura, estado, designs e planos
.github/             Modelos de issues e pull requests
```

`artifacts/`, `dist/`, `work/`, memórias locais e exercícios externos não são distribuídos pelo Git. Não envie PDFs, bytecode ou materiais de terceiros sem autorização para redistribuição.

## Licença

A licença do código ainda será definida pelo responsável pelo projeto. Não há uma licença de código aberto concedida neste repositório por enquanto. Modelo, ferramentas e materiais de terceiros possuem termos próprios; sua inclusão em uma distribuição deve ser verificada separadamente.
