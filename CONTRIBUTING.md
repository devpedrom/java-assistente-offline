# Como contribuir

Contribuições de colegas, inclusive com auxílio de IA, são bem-vindas. Comece por [README.md](README.md), [AGENTS.md](AGENTS.md), [arquitetura](docs/ARQUITETURA.md) e [estado do projeto](docs/ESTADO-DO-PROJETO.md). Para uma nova conversa com IA, use [este roteiro](docs/CONTEXTO-PARA-IA.md).

## Fluxo de trabalho

1. Abra uma issue com o problema, exemplo reproduzível e resultado esperado. Para mudanças maiores, alinhe o escopo com o responsável antes de implementar.
2. Atualize seu clone e crie uma branch curta por assunto, por exemplo `git switch -c melhoria/descricao-curta`. Se não tiver acesso de escrita, trabalhe em um fork e abra um pull request.
3. Confira `git status --short` e `git diff` antes de editar. Preserve alterações de outras pessoas e não use reset ou limpeza destrutiva para preparar seu trabalho.
4. Faça a menor alteração que resolve o problema. Separe refatorações e mudanças funcionais quando puderem ser revisadas independentemente.
5. Execute os testes relevantes e depois a suíte completa. Registre comando, plataforma, contagens e limitações no pull request.
6. Revise `git diff --check` e o diff completo antes do commit. Adicione arquivos explicitamente; não inclua dados locais ou artefatos binários.
7. Abra um pull request explicando problema, solução e evidências. Aguarde a revisão do responsável; não faça push forçado em branches compartilhadas.

Não é necessário instalar dependências para rodar os testes puramente Python. Instalações, serviços e publicação realizados por uma IA exigem autorização conforme [AGENTS.md](AGENTS.md).

## Testes

Na raiz do projeto, Linux:

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_profile -v
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

PowerShell:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
python -m unittest tests.unit.test_profile -v
python -m unittest discover -s tests -v
```

Troque `tests.unit.test_profile` pelo módulo que cobre a mudança. Para alterações de empacotamento, execute também `tests.packaging.test_installer`, faça o build com artefatos já preparados e rode a aceitação no Linux/WSL, conforme [AGENTS.md](AGENTS.md). Não baixe nem regenere artefatos implicitamente.

Se o temporário do sistema estiver bloqueado, crie uma pasta local ignorada e use-a apenas na sessão:

```powershell
New-Item -ItemType Directory -Force work/test-temp | Out-Null
$env:TEMP=(Resolve-Path work/test-temp).Path
$env:TMP=$env:TEMP
```

Registre esse ajuste no resultado. Falha de ambiente, timeout ou teste pulado não é aprovação. Diferencie Windows, WSL e Linux Mint real. A aceitação de hardware precisa ser repetida em máquina CPU-only com 4–6 GB de RAM e mídia real.

## Regras de implementação

- Python 3.10+ e fontes Java gerados compatíveis com Java 8.
- Preserve nomes, tipos, visibilidade e assinaturas do contrato PDF/UML.
- Mantenha o controlador como único executor de ações validadas. Não dê shell ao modelo.
- Preserve o limite de escrita, os timeouts e o funcionamento offline.
- Não codifique regras de Frota ou de qualquer exercício particular no produto. Use fixtures sintéticas variadas.
- Acrescente testes que reproduzam regressões funcionais; não adapte a expectativa apenas para fazer o teste passar.
- Atualize a documentação quando alterar comandos, configuração, instalação ou limites.
- Preserve `CRITERIOS_GERAIS.md` e as configurações do usuário em reinstalações.

## Trabalho com IA

Você é responsável por revisar o diff e as evidências produzidas pela IA. Informe no pull request quais partes tiveram auxílio de IA e o que você conferiu. Não é necessário publicar conversas completas, prompts privados ou raciocínio interno. Compartilhe apenas decisões técnicas, reprodução e resultados úteis.

Antes de encerrar uma tarefa, deixe um resumo com objetivo, arquivos alterados, comandos executados, resultado e pendências. Se uma conclusão mudar, atualize o documento que a contém para evitar instruções contraditórias.

## Conteúdo público

Não envie credenciais, `.env`, logs de conversa, bancos de memória, caminhos pessoais, PDFs privados, bytecode de terceiros, modelos GGUF ou bundles. O `.gitignore` evita inclusão acidental de algumas dessas categorias, mas não substitui a revisão do conteúdo e do histórico.

Enquanto a licença estiver pendente, alinhe com o responsável as condições para contribuições e redistribuição. Não presuma que um repositório público concede uma licença de código aberto.
