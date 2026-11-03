# Núcleo genérico, perfil de competição e adaptador Java 8

- **Data:** 2026-10-23
- **Status:** proposto; aguarda aprovação do parceiro humano antes de `writing-plans`
- **Base:** commit `277d089` (branch `master`) + estado não commitado descrito na seção 9
- **Entrega:** worktree isolada na branch `opencode`, sem commit nesta fase
- **Substitui parcialmente:** a afirmação de escopo "linguagens diferentes de Java" fora de escopo, em `docs/superpowers/specs/2026-10-21-assistente-java-offline-design.md` §12. Este design passa a admitir núcleo genérico com Java 8 como único adaptador real desta entrega.

## 1. Intenção e por quê

O produto já instala e inicia offline, compila e executa Java 8 e registra evidências honestas. O que falta é o que decide a competição: **interpretar enunciados diferentes do formato do fixture** e **provar o que foi entregue** sem depender de heurísticas escritas para um exercício.

Este design troca o monólito de resolução por um núcleo determinístico com contrato genérico, perfil declarativo de competição e um adaptador Java 8. O núcleo não conhece `javac`, `.java`, `main` nem nomes de exercício; o adaptador Java 8 conhece. Uma segunda linguagem não é implementada agora, mas a fronteira é provada por um adaptador-stub em teste.

## 2. Resultado esperado para o usuário

1. Na competição, `java-assistente` abre na pasta do exercício, lê o PDF com `/pdf` e mostra o que reconheceu, separando confirmado de inferido.
2. Se não houver estrutura confiável, o assistente **para e pergunta** — nunca gera, nunca compila arquivos antigos e nunca diz "solução concluída".
3. Com estrutura confirmada, ele gera uma unidade por vez, compila, valida contra o contrato, executa a entrada quando existe e relata exatamente o que foi e o que não foi verificado.
4. Antes da competição, linguagem, compilador, bibliotecas, limites, comandos e orçamento de contexto são ajustáveis em um arquivo de perfil, sem tocar no código.
5. O comportamento atual que funciona continua funcionando; os testes existentes migram, não desaparecem.

## 3. Escopo

### Dentro

- Núcleo genérico: especificação do enunciado, regras de requisito, orçamento de contexto, pipeline por estágios, registro de comandos.
- Perfil declarativo global com override opcional por projeto, validação e precedência.
- Adaptador Java 8 real, reaproveitando `java/toolchain.py`, `java/validator.py` e `uml/extract.py`.
- Adaptador-stub somente para testes.
- Remoção das heurísticas específicas do fixture por regras genéricas com testes de regressão.
- Falha explícita quando não há contrato confiável.
- Orçamento real de contexto para 4096 tokens.
- Empacotamento do perfil no bundle e preservação na reinstalação.
- Documentação de operação e do perfil.

### Fora

- Memória `.assistente` completa (retomada entre sessões, diário, reconciliação, reconstrução do SQLite). Fica para a entrega seguinte, conforme decisão aprovada.
- Segunda linguagem real.
- UML visual: interpretar caixas, setas e relações espaciais a partir de imagem renderizada.
- Testes oficiais dos jurados.
- Alterar o modelo GGUF, o runtime llama.cpp ou o limite de 2 GB.
- Qualquer commit, push, publicação, download ou instalação.

### Anti-metas

- Não criar DSL de regras, plugin dinâmico ou carregamento de código pelo perfil.
- Não mover arquivos sem necessidade; mover só quando o nome impede o núcleo de ser genérico.
- Não prometer aprovação em teste secreto.
- Não usar o PDF de exemplo como requisito de produto.

## 4. Restrições e invariantes obrigatórios

Herdados de `AGENTS.md` e das specs; nenhum é negociável:

- Instalação e uso 100% offline, sem API, `sudo`, rede ou pendrive conectado após instalar.
- O diretório de trabalho atual é a raiz imutável e o limite de escrita; caminhos absolutos, `..` e escape por symlink são recusados.
- O modelo não tem shell; o controlador executa apenas ações validadas e allowlisted.
- Compatibilidade Java 8 e preservação exata de nomes, tipos, visibilidades, assinaturas e herança do PDF/UML.
- Nenhuma classe, fórmula, nome ou regra do exercício Frota no produto.
- Modelo, ferramentas nativas, JDK e instalador continuam empacotados; distribuição ≤ 2 GiB.
- Compilação não prova regra de negócio; o relatório mantém as cinco categorias de evidência.
- Nenhum dado sensível em fonte, memória, log ou documentação.
- Nesta fase, nenhuma alteração no checkout original.

## 5. Diagnóstico verificado (com evidências)

1. **Heurísticas de exercício no produto.** `session.py:81-134` (`_semantic_issues`) e `session.py:367-394` (`_focused_requirements`) embutem "aumenta em 100%", "reduzida pela metade", "um quarto", "nunca ... maior que" e "autonomia"/`super.autonomia()`. Viola o invariante da seção 4. Deve ser **substituído por regras genéricas**, não apenas apagado.
2. **Dependência do formato-fixture.** `_required_java_names` (`session.py:242-250`) só reconhece `classe X (main)`; `UmlExtractor` (`uml/extract.py`) só reconhece `CLASSE:`, `class`, `+ membro(): Tipo`, `herda de:` e `<|--`. Em enunciado fora desse formato, o contrato sai vazio e "Resolva" produz silêncio ou compila arquivos antigos.
3. **Contexto sem orçamento.** `build_context` (`criteria.py:44-67`) concatena critérios + 12k chars de PDF + 6k de fontes + memória sem limite; a janela é 4096 tokens (`runtime.py:27`) e `max_tokens=384` (`client.py:35`). Uma classe Java real pode ser truncada.
4. **Conclusão sem prova.** `_guided_solve` (`session.py:481-574`) declara "Solução concluída" quando todas as fontes já existiam e compilaram, mesmo sem contrato confiável e sem validar regra alguma.
5. **Recuperação limitada.** `History` só existe em memória (`history.py:16`); `/desfazer` morre ao reiniciar. `store.py:21-22` deriva identidade do caminho, então mover a pasta perde o projeto. A memória `.assistente` aprovada não está implementada.
6. **Acoplamento de resolução.** `session.py` (835 linhas) acumula chat, comandos, intake, geração, reparo, validação, execução, relatório e prompt. `java/toolchain.py` e `java/validator.py` já são quase núcleo e podem ser preservados.
7. **Comandos fixos.** `/pdf`, `/desfazer`, `/relatorio`, `/ajuda`, `/sair` estão em `session.py:814-835`; não há configuração.

## 6. Abordagens consideradas

| Abordagem | O que é | Custo | Risco | Veredito |
|---|---|---|---|---|
| A. Núcleo por estágios + perfil + adaptador | Pipeline determinístico; modelo chamado por unidade; contrato genérico; perfil validado | Médio | Médio (mexe em `session.py` já modificado) | **Escolhida** |
| B. Evolução mínima do agente | Mantém o loop livre de ações; extrai perfil e adaptador; remove heurísticas | Baixo | Baixo | Não atinge confiabilidade: o loop livre é a parte menos previsível com 3B |
| C. Especificação verificável com testes gerados | Cada requisito vira asserção estrutural e comportamental gerada | Alto | Alto | Adiada: pedir ao 3B para inventar saídas esperadas cria falsa confiança |

**Decisão:** A, aprovada pelo parceiro humano em 2026-10-23, com os sete ajustes da seção 18.

## 7. Arquitetura escolhida

### 7.1 Estrutura de módulos

Criar:

```text
src/java_assistant/
  profile.py                  # esquema, carga, validação, merge global→projeto
  core/
    __init__.py
    spec.py                   # Specification, Unit, Member, Relationship, Requirement
    facts.py                  # extração de requisitos genéricos e checagens de fonte
    budget.py                 # orçamento de contexto por seção
    solver.py                 # pipeline por estágios
    commands.py               # registro de comandos vindo do perfil
  adapters/
    __init__.py               # registries e resolução por id
    base.py                   # LanguageAdapter, Toolchain, CompileResult, RunResult
    java8.py                  # adaptador Java 8 (prompt, parse, reparo, matchers)
    stub.py                   # adaptador de teste, nunca no perfil de produção
```

Preservar sem mover: `workspace/*`, `model/*`, `memory/*`, `pdf/*`, `review/report.py`, `java/toolchain.py`, `java/validator.py`, `uml/extract.py`, `criteria.py`, `config.py`, `cli.py`.

`shortcut: manter uml/extract.py no caminho atual como extrator do adaptador Java; renomear quando existir um segundo formato real de enunciado.`

### 7.2 Especificação genérica (`core/spec.py`)

Substitui `uml/models.py` (removido) e é serializável de forma determinística.

```python
@dataclass(frozen=True)
class Requirement:
    text: str                      # verbatim do PDF ou do usuário, nunca reescrito
    origin: str                    # "pdf-text" | "pdf-ocr" | "uml" | "user"
    confidence: float              # 0.0..1.0
    scope: str | None              # None = enunciado inteiro; senão nome da unidade

@dataclass(frozen=True)
class Member:
    name: str
    kind: str                      # "field" | "constructor" | "method"
    type_name: str
    visibility: str                # "public" | "private" | "protected" | "package"
    parameters: tuple[tuple[str, str], ...] = ()
    modifiers: tuple[str, ...] = ()  # "static" | "abstract" | "final" | ""

@dataclass(frozen=True)
class Unit:
    name: str
    kind: str                      # "class" | "interface" | "enum"
    members: tuple[Member, ...]
    modifiers: tuple[str, ...] = ()

@dataclass(frozen=True)
class Relationship:
    parent: str
    child: str
    kind: str                      # "inheritance" | "implements" | "association" | ...
    confidence: float
    alternatives: tuple[str, ...] = ()

@dataclass(frozen=True)
class Specification:
    units: tuple[Unit, ...]
    relationships: tuple[Relationship, ...]
    requirements: tuple[Requirement, ...]
    warnings: tuple[str, ...] = ()
```

Regras:

- Nomes vazios ou não identificadores são rejeitados na construção.
- Round-trip `to_dict`/`from_dict` estável, com ordem preservada e cópias defensivas.
- `kind` é validado contra um conjunto fechado.
- Nada de `Java*` no núcleo. O adaptador traduz.

**Derivação de escopo.** O texto do PDF é dividido em seções por cabeçalho cujo texto normalizado (sem acento, sem caixa) é igual ao nome de uma unidade. Um requisito pertence à unidade cuja seção o contém; texto antes do primeiro cabeçalho, ou que não menciona unidade, recebe `scope=None` e vale como regra geral no prompt, sem gerar asserção por unidade. Não há heurística por palavra-chave de domínio.

**Escala de confiança (por item, não por especificação):**

| Valor | Origem |
|---|---|
| 1,0 | confirmado explicitamente pelo usuário |
| 0,98 | notação UML explícita na camada textual |
| 0,80 | notação explícita obtida por OCR (força confirmação) |
| 0,50 | relação ambígua (`--`), já existente |

`trusted` exige **todas** as unidades com confiança ≥ 0,9, nenhuma relação ambígua e ao menos um membro por unidade ou confirmação do usuário.

### 7.3 Perfil declarativo (`profile.py`)

**Local e precedência**

1. `~/.config/java-assistente/perfil.json` — global, criado pelo instalador somente se ausente.
2. `<projeto>/.assistente/perfil.json` — override opcional, lido quando existir. Não é criado automaticamente.
3. O override é mesclado campo a campo sobre o global; listas substituem, não concatenam.
4. Precedência de conteúdo: políticas do controlador > `CRITERIOS_GERAIS.md` integral > perfil técnico > requisitos confirmados do PDF > pedido atual > memória.

**Esquema (versão 1)**

```json
{
  "schema_version": 1,
  "language": { "id": "java8", "source_extension": ".java" },
  "toolchain": {
    "compiler": "tools/native/bin/javac",
    "runtime": "tools/native/bin/java",
    "inspector": "tools/native/bin/javap"
  },
  "libraries": [],
  "limits": {
    "compile_timeout_s": 30,
    "run_timeout_s": 15,
    "inspect_timeout_s": 10,
    "repair_attempts": 2,
    "max_files": 40,
    "context_tokens": 4096,
    "output_tokens": 640
  },
  "context": {
    "chars_per_token": 3.5,
    "sections": {
      "protocol": 220,
      "criteria": 400,
      "spec_target": 520,
      "parents": 800,
      "pdf_excerpt": 520,
      "rules": 300,
      "memory": 120,
      "user_request": 180
    }
  },
  "commands": {
    "pdf": ["/pdf"],
    "undo": ["/desfazer"],
    "report": ["/relatorio"],
    "profile": ["/perfil"],
    "help": ["/ajuda"],
    "exit": ["/sair", "sair"]
  }
}
```

**Caminhos:** relativos são resolvidos a partir de `JAVA_ASSISTANT_HOME`; absolutos são aceitos. Esquema, faixas e aliases são validados na carga, antes do primeiro prompt; a existência dos caminhos do toolchain e das bibliotecas é verificada **ao iniciar o assistente, antes do primeiro prompt**, o que falha cedo e nomeia o caminho testado (testes constroem a sessão diretamente e não passam por `cli.main`, então não dependem do bundle). `libraries` é lista de `.jar`/diretórios entregues ao compilador e ao runtime; não amplia o limite de escrita.

**Validação (antes de qualquer geração):**

- `schema_version` exatamente 1; chave desconhecida é erro com a lista de chaves aceitas.
- `language.id` precisa resolver para um adaptador registrado; ids disponíveis aparecem na mensagem.
- Limites são inteiros dentro de faixas explícitas: timeouts 1..600; `repair_attempts` 0..5; `context_tokens` 512..8192; `output_tokens` 64..2048 e sempre menor que `context_tokens`.
- `chars_per_token` entre 2.0 e 6.0.
- Comandos: ids conhecidos; aliases não vazios, únicos entre si e sem colisão entre comandos. O perfil **renomeia ou desabilita** comandos conhecidos; não inventa comportamento novo.
- Nenhum comando de shell é aceito no perfil; o controlador constrói argv.

**Instalação:** `packaging/linux/perfil-padrao.json` entra no runtime em `share/`; `instalar.sh` copia para `$APP_CONFIG/perfil.json` se ausente, nunca sobrescreve. Reinstalação preserva o arquivo editado.

### 7.4 Pipeline (`core/solver.py`)

Estágios com pré-condições explícitas:

1. **Intake** — recebe `PdfEvidence` e produz `Specification` via extrator do adaptador. Classifica:
   - `trusted`: ≥ 1 unidade, todas com nome válido e origem confirmada (UML com confiança ≥ 0,9 ou confirmação do usuário);
   - `needs_confirmation`: existe estrutura, mas há ambiguidade, OCR com aviso ou unidade sem membros;
   - `no_contract`: nenhuma unidade reconhecida.
2. **Plano** — ordena unidades por dependência (pais, interfaces, tipos de campo), alfabética dentro do mesmo nível; detecta ciclo e unidade duplicada. Define a entrada somente como unidade que declara método `main` ou que o usuário nomear. Não usa regex de `(main)` no texto.
3. **Gerar(unidade)** — uma chamada ao modelo por unidade; o adaptador extrai exatamente uma unidade com o nome público exigido. Resposta inválida: uma nova tentativa com o erro específico; depois, falha explícita nomeando o que veio.
4. **Verificar** — asserções estruturais do adaptador via inspector + compilação conjunta de todas as fontes `.java` da raiz, como hoje (compilar subconjunto tornaria a verificação incompleta por dependências). Diagnóstico vindo de arquivo fora da especificação interrompe com mensagem que nomeia o arquivo e **nunca** o reescreve. Cada evidência é registrada com hash das fontes verificadas.
5. **Reparar** — limitado por `repair_attempts`. Só repara arquivo gerado nesta execução ou arquivo pré-existente que pertença à especificação e seja alvo do diagnóstico; nesse caso, registra conteúdo anterior via `History` e mostra a diferença. Arquivo não gerado pelo assistente e fora da especificação nunca é reescrito: é reportado.
6. **Executar** — somente se houver entrada definida. Timeout do perfil; classes em diretório temporário, fora da entrega.
7. **Relatório** — ver 7.9.

**Roteamento.** Pedido de geração com contrato `trusted` → solver. Pedido de geração sem contrato → intake (pergunta, nada é gerado). Conversa, pergunta geral, microajuste e criação avulsa **sem PDF** → loop de ações existente, preservado, com os limites do perfil; esse loop responde ao pedido, mas não declara "solução concluída" nem valida contrato.

**Semântica de falha (ajuste 2):**

- `no_contract` → mensagem explícita: o que foi lido, o que não foi reconhecido, e pedido de confirmação no formato textual aceito (reutiliza `UmlExtractor` sobre a resposta do usuário). Nenhuma chamada de geração, nenhuma compilação.
- `needs_confirmation` → pergunta numerada; bloqueia geração até resolver. Ambiguidade já existente continua igual.
- Falha de geração/compilação/validação → interrompe com diagnóstico e arquivos preservados; nunca "solução concluída".
- Arquivos existentes compilados por comando explícito → mensagem "arquivos existentes compilados; contrato não validado", nunca "solução concluída".
- "Solução concluída" só é permitida quando houve geração ou validação estrutural contra especificação confiável **e** compilação aprovada **e** execução aprovada quando há entrada.

### 7.5 Regras genéricas que substituem as heurísticas (ajuste 1)

Nenhuma regra conhece nome de classe, atributo ou exercício. Todas operam sobre `Requirement.text` verbatim, `Specification` e fonte gerada, com matchers fornecidos pelo adaptador.

| Comportamento atual | Substituição genérica | Regressão |
|---|---|---|
| `aumenta em X%` → fator `1 + X/100` | `ArithmeticRule` extrai percentual, "dobra" (2.0), "metade" (0.5), "um quarto" (0.75) de qualquer requisito; fator vai ao prompt e é checado na fonte pelo matcher do adaptador | Testes de 100%, 50%, metade, um quarto; casos negativos |
| `reduzida pela metade` → `* 0.5` | mesma regra, sem vocabulário de domínio | migrado |
| `nunca ... maior que` → `IllegalArgumentException` | `InvariantRule(kind="upper_bound")`: exige comparação e ação explícita (throw, `Math.min` ou retorno condicional) | migrado |
| `autonomia` repetindo efeito de `super` | `OverrideRule` derivada da especificação: para método declarado na unidade e no pai, se nenhum requisito do escopo menciona o método, proíbe aritmética sobre `super.metodo(...)` e exige a chamada a `super` | migrado, sem a palavra "autonomia" |
| `FATOS ARITMÉTICOS OBRIGATÓRIOS`, `VERIFICAÇÃO GERAL`, aviso de autonomia | seções genéricas montadas a partir das regras extraídas e da especificação | prompt testado |
| `_diagnostic_guidance` int→Double | dica do adaptador Java para diagnósticos comuns do `javac` | migrado |
| `classe X (main)` | entrada = método `main` na especificação ou escolha do usuário | teste de entrada com nome próprio |

Um teste dedicado varre `src/` e falha se aparecer `Frota`, `Hatch`, `Pickup`, `calculaVolume` ou `autonomia` como regra de produto. Fixtures em `tests/` continuam podendo usar esses nomes.

### 7.6 Orçamento de contexto (ajuste 3)

- `context_tokens` do perfil alimenta `RuntimeConfig`; `output_tokens` alimenta o cliente (substitui o 384 fixo).
- Margem de segurança fixa de 128 tokens para metadados do template.
- Entrada disponível = `context_tokens - output_tokens - 128`. Com os padrões: 4096 − 640 − 128 = **3328 tokens**.
- Cada seção tem teto em tokens, convertido para caracteres por `chars_per_token` (padrão 3,5, conservador).
- Ordem de prioridade: `protocol`, `criteria`, `spec_target`, `user_request`, `rules`, `parents`, `pdf_excerpt`, `memory`.
- Se a soma exceder a entrada disponível, remove-se a seção inteira de menor prioridade nesta ordem: `memory`, `pdf_excerpt`, `parents`, `rules`. Nunca se remove `protocol`, `criteria`, `spec_target` ou `user_request`.
- Cada seção é truncada no último limite de linha antes do teto, com marcador `[... truncado: N caracteres omitidos]`.
- `criteria` **não é truncado**: os critérios são carregados integralmente por exigência da spec. Se ultrapassarem o teto, a implementação aborta com mensagem objetiva pedindo redução, em vez de omitir regra do jurado. O teto padrão é 400 tokens (~1400 caracteres) porque o `CRITERIOS_GERAIS.md` embarcado tem 1314 caracteres; o template precisa caber no teto padrão.
- Seções omitidas e truncadas são registradas no relatório em "Contexto omitido (limite de tokens)".
- Testes: soma ≤ orçamento; prioridades preservadas; ordem de descarte; critérios grandes falham explicitamente; padrão 4096 coerente entre runtime e orçamento.

### 7.7 Adaptadores

```python
class Toolchain(Protocol):
    def compile(self, sources: list[Path]) -> CompileResult: ...
    def run(self, entry: str, timeout_s: int, stdin: str = "",
            args: tuple[str, ...] = ()) -> RunResult: ...
    def inspect(self, symbol: str, timeout_s: int = 10) -> str: ...

class LanguageAdapter(Protocol):
    id: str
    source_extension: str
    def system_protocol(self) -> str: ...
    def build_unit_prompt(self, spec, unit, rules, sections) -> list[Message]: ...
    def parse_unit_source(self, reply: str, unit: Unit) -> str: ...
    def structural_issues(self, spec, toolchain) -> tuple[str, ...]: ...
    def repair_target(self, diagnostics: str) -> str | None: ...
    def diagnostic_hint(self, diagnostics: str) -> str: ...
    def entry_point(self, spec) -> str | None: ...
    def matchers(self) -> SourceMatchers: ...   # factor, guard, super_call
```

- `CompileResult` e `RunResult` passam para `adapters/base.py`; `java/toolchain.py` os reexporta para não quebrar imports existentes.
- Java 8: implementa tudo reaproveitando `JavaToolchain` (`compile/run/inspect`), `ContractValidator` (asserções `javap`) e `UmlExtractor` (texto/OCR). Recebe `libraries` como classpath.
- Stub: `adapters/stub.py` implementa a interface com compilador falso e fonte trivial; é registrado apenas quando `allow_stub=True`, usado só em teste. Prova que o núcleo não importa Java.
- `resolve_adapter(id)` devolve adaptador registrado ou erro listando ids.

### 7.8 Comandos configuráveis

- `core/commands.py` monta o mapa alias → id a partir do perfil, valida colisões e devolve ajuda gerada.
- Os cinco comandos atuais mantêm semântica: `/pdf`, `/desfazer`, `/relatorio`, `/ajuda`, `/sair` (+ `sair`).
- Novo `/perfil`: somente leitura, mostra caminho efetivo, origem (global/projeto), adaptador, limites e comandos; não imprime segredos nem caminho de pendrive.
- Comando desconhecido → ajuda gerada do perfil, com os aliases ativos.
- Renomear ou desabilitar comando não altera o comportamento interno; só o alias.
- Omitir um comando do perfil o desabilita; lista de aliases vazia é erro de validação. `exit` é obrigatório e não pode ser desabilitado: é a saída garantida além de EOF e `Ctrl+C`.

### 7.9 Evidências e honestidade

`review/report.py` mantém as cinco seções atuais e ganha duas:

- **Contexto omitido (limite de tokens):** seções removidas/truncadas.
- **Observações de verificação:** contrato ausente, arquivo não gerado pelo assistente, adaptador stub, entrada não executada.

Regras de texto:

- Compilar arquivo existente não vira "solução concluída".
- Validar estrutura não vira "regra de negócio correta".
- Nunca mencionar aprovação oficial.
- OCR continua com aviso explícito; relação espacial não interpretada é declarada como não implementada.

### 7.10 Recuperação e repetibilidade

- Escrita atômica e confinada já existentes em `workspace/files.py` são reutilizadas; nada novo de I/O.
- Reparo limitado e direcionado; três falhas consecutivas continuam interrompendo o loop de chat.
- Ordenação determinística de unidades, fontes e seções.
- Normalização `\r\n` → `\n` na extração de fonte e nos hashes de evidência.
- Nenhum timestamp em asserção de teste; relógio injetável quando necessário.
- Porta efêmera em `127.0.0.1` (já existente).
- Duas execuções da mesma fixture produzem as mesmas evidências e os mesmos hashes.

## 8. Mudanças por arquivo

| Arquivo | Ação | Motivo |
|---|---|---|
| `src/java_assistant/profile.py` | criar | esquema, validação, merge, caminhos |
| `src/java_assistant/core/spec.py` | criar | contrato genérico serializável |
| `src/java_assistant/core/facts.py` | criar | regras genéricas substitutas das heurísticas |
| `src/java_assistant/core/budget.py` | criar | orçamento de contexto |
| `src/java_assistant/core/solver.py` | criar | pipeline por estágios |
| `src/java_assistant/core/commands.py` | criar | comandos vindos do perfil |
| `src/java_assistant/adapters/base.py` | criar | protocolos e resultados |
| `src/java_assistant/adapters/java8.py` | criar | adaptador Java 8 |
| `src/java_assistant/adapters/stub.py` | criar | adaptador de teste |
| `src/java_assistant/uml/models.py` | remover | substituído por `core/spec.py`; imports atualizados |
| `src/java_assistant/uml/extract.py` | modificar | emitir `Specification`, aceitar `interface` e `implements` |
| `src/java_assistant/uml/__init__.py` | modificar | exportar o novo modelo |
| `src/java_assistant/java/toolchain.py` | modificar | resultados em `adapters/base.py`, classpath de bibliotecas |
| `src/java_assistant/java/validator.py` | modificar | consumir `Specification` |
| `src/java_assistant/session.py` | modificar | vira casca de chat/intake; remove heurísticas, prompts e geração |
| `src/java_assistant/criteria.py` | modificar | `build_context` com orçamento |
| `src/java_assistant/cli.py` | modificar | carregar perfil, resolver adaptador, montar solver |
| `src/java_assistant/config.py` | modificar | caminho do perfil global e override |
| `src/java_assistant/review/report.py` | modificar | seções de omissão/observação |
| `packaging/linux/perfil-padrao.json` | criar | perfil padrão empacotado |
| `packaging/linux/assemble_runtime.py` | modificar | incluir perfil em `share/` |
| `packaging/linux/instalar.sh` | modificar | copiar perfil se ausente |
| `docs/USO-RAPIDO.md` | modificar | perfil, comandos, limite de UML visual |
| `docs/PERFIL-COMPETICAO.md` | criar | referência completa do perfil |
| `docs/ARTEFATOS-LINUX.md` | modificar | perfil no bundle |
| `tests/acceptance/run-offline.sh` | modificar | exigir perfil criado e preservado |
| `tests/acceptance/checklist.md` | modificar | novos gates |
| `tests/unit/test_profile.py` | criar | validação e precedência |
| `tests/unit/core/test_spec.py` | criar | round-trip e rejeições |
| `tests/unit/core/test_facts.py` | criar | regras genéricas |
| `tests/unit/core/test_budget.py` | criar | orçamento |
| `tests/unit/test_no_fixture_leak.py` | criar | invariante anti-hard-code |
| `tests/unit/adapters/test_registry.py` | criar | resolução e stub |
| `tests/unit/adapters/test_java8.py` | criar | parse, reparo, entrada, matchers |
| `tests/unit/test_commands.py` | criar | aliases e ajuda |
| `tests/integration/test_intake.py` | criar | sem contrato, confirmação, plano |
| `tests/integration/test_solver.py` | criar | pipeline, reparo, honestidade |
| `tests/integration/test_enunciados.py` | criar | cinco fixtures distintos |
| `tests/integration/test_session_flow.py` | modificar | atualizar para a casca e preservar regressões |
| `tests/unit/test_guided_generation.py` | modificar | migrar para regras genéricas, sem nomes do fixture |
| `tests/unit/test_criteria.py` | modificar | orçamento no lugar de concatenação livre |
| `tests/integration/test_pdf_uml.py`, `test_ambiguous_uml.py`, `test_java_toolchain.py` | modificar | importar `core/spec.py` |
| `tests/fixtures/enunciados/**` | criar | cinco cenários determinísticos |

Nenhuma alteração em `packaging/linux/build-bundle.sh`, `manifest.sha256` gerado, `memory/`, `model/`, `pdf/` ou `workspace/` além do listado.

## 9. Estado não commitado e worktree (ajuste 5)

### Inventário confirmado em 2026-10-23

- HEAD: `277d08926525dfc70f7d2bfdeff0e6529877e4fb` (branch `master`).
- **24 arquivos modificados** (`git diff --stat`: 1112 inserções, 114 remoções).
- **3 arquivos não rastreados:**
  1. `AGENTS.md`
  2. `packaging/linux/assemble_runtime.py`
  3. `tests/unit/test_guided_generation.py`
- `git diff --cached` vazio: nada staged.
- Total do inventário: 27 entradas.

Existe uma worktree criada pelo harness em `.local/share/opencode/worktree/9ecf82/shiny-mountain`, no mesmo commit e limpa. Ela **não** contém as alterações não commitadas e não será usada nem alterada. A worktree de entrega é a nova, em `Downloads\java-assistente-offline-opencode`, branch `opencode`.

### Reprodução na worktree, sem tocar no original

1. Criar `<diretorio-local-de-evidencias>/baseline\`.
2. Salvar `inventory.txt` com `git status --porcelain=v1` (27 linhas) e `git diff --stat`.
3. Salvar `worktree.patch` com `git diff --binary --no-color` (somente os 24 rastreados).
4. Salvar `hashes-before.txt` com SHA-256 dos 27 arquivos, em ordem de caminho relativo.
5. `git worktree add -b opencode "../java-assistente-offline-opencode" 277d089`.
6. Aplicar `worktree.patch` com `git -C <worktree> apply --whitespace=nowarn`.
7. Copiar os 3 não rastreados byte a byte para o mesmo caminho relativo.
8. Verificar, antes de editar:
   - SHA-256 dos 27 arquivos da worktree idêntico a `hashes-before.txt` (diff vazio);
   - `git -C <worktree> status --porcelain` idêntico a `inventory.txt`;
   - `git -C <worktree> diff --stat` idêntico ao original;
   - `git -C <original> status --porcelain` inalterado;
   - suíte completa na worktree: 63 testes, OK, 2 skips.
9. Só então iniciar a primeira tarefa.

Falha em qualquer verificação interrompe o processo e é relatada; nada é copiado manualmente por cima de conteúdo divergente. `.gitattributes` normaliza `.py/.md/.java/.sh` para LF, mas a prova é o hash, não a suposição.

**Risco assumido:** como não há commit autorizado, a worktree começa suja. Cada revisão de tarefa recebe apenas o diff dos arquivos que a tarefa tocou e a comparação de hash com `hashes-before.txt`; nunca o diff inteiro da árvore. Se o parceiro autorizar um commit de baseline no futuro, ele será feito antes da primeira tarefa.

## 10. Tarefas derivadas do design

Ordem de dependência; cada tarefa começa por teste que falha, implementa o mínimo completo, roda os testes relacionados e passa por revisão independente do GLM.

| # | Tarefa | Teste primeiro | Depende de |
|---|---|---|---|
| T1 | Perfil: esquema, validação, merge global→projeto, caminhos | `tests/unit/test_profile.py` | — |
| T2 | Especificação genérica e remoção de `uml/models.py` | `tests/unit/core/test_spec.py` | — |
| T3 | Protocolos de adaptador, registry, stub | `tests/unit/adapters/test_registry.py` | T2 |
| T4 | Adaptador Java 8: parse, reparo, entrada, matchers, dicas | `tests/unit/adapters/test_java8.py` | T3 |
| T5 | Regras genéricas e migração dos testes de geração guiada | `tests/unit/core/test_facts.py`, `tests/unit/test_no_fixture_leak.py` | T2, T4 |
| T6 | Orçamento de contexto | `tests/unit/core/test_budget.py` | T1 |
| T7 | Intake, confiança, confirmação e plano | `tests/integration/test_intake.py` | T2, T4 |
| T8 | Solver: gerar, verificar, reparar, executar, relatar | `tests/integration/test_solver.py` | T5, T6, T7 |
| T9 | Comandos configuráveis e `/perfil` | `tests/unit/test_commands.py` | T1 |
| T10 | Sessão enxuta e atualização das regressões | `tests/integration/test_session_flow.py` | T8, T9 |
| T11 | Cinco enunciados distintos end-to-end | `tests/integration/test_enunciados.py` | T8 |
| T12 | Empacotamento, documentação e aceitação | `tests/packaging/test_installer.py`, `tests/acceptance/*` | T9, T11 |
| T13 | Verificação final, repetibilidade e registro de limitações | suíte completa, duas execuções | T12 |

O detalhamento passo a passo, com trechos de teste e comandos exatos, sai de `superpowers:writing-plans` depois da aprovação deste design.

## 11. Cinco enunciados distintos (fixtures determinísticas)

Cada fixture contém `enunciado.txt`, `respostas_modelo.json`, `contrato_esperado.json` e `casos_execucao.json`. Nenhum usa rede ou modelo real. Cada fixture cobre **três caminhos**: feliz, um reparo (resposta inicial inválida ou divergente que consome `repair_attempts`) e um caso negativo que deve falhar honestamente (fator errado, ausência de guarda de limite, assinatura divergente ou ausência de unidade).

1. **Herança e polimorfismo:** `Forma` abstrata com `area(): double`; `Circulo` e `Retangulo extends Forma`; `Desenho` com coleção e laço polimórfico. Prova `extends`, tipo do retorno, assinatura e compilação.
2. **Composição:** `Time` com coleção privada de `Jogador`, sem herança. Prova campo privado de tipo composto, ordem de geração e ausência de `extends` inventado.
3. **Interface:** `Pagavel` com `pagar(double): boolean`; `Boleto` e `Cartao implements Pagavel`. Prova `interface` real, `implements` exato e rejeição de assinatura divergente.
4. **Entrada/saída:** `ConversorTemperatura` lê `double` de `Scanner(System.in)` e imprime. Prova execução com stdin fixo, saída esperada e encoding UTF-8.
5. **Regra aritmética com limites:** bônus com fator 1,5, teto e exceção acima do teto. Prova borda exata, teto+1, e que a regra vem do perfil/requisito, não de palavras-chave de exercício.

## 12. Regressões obrigatórias preservadas

1. PDF por número, inclusive um único arquivo, com resposta inválida reexibindo a lista.
2. Ambiguidade bloqueia geração até a escolha; alternativas registradas.
3. Extração de fonte simples, cercada e em `<write_file>`, com rejeição de duas classes públicas.
4. Uma requisição pode criar mais de três arquivos no modo de ações.
5. `/desfazer` não sobrescreve edição posterior do usuário.
6. Caminho com acento e espaço funciona; escrita fora da raiz é recusada.
7. Timeout de execução encerra o processo Java iniciado pelo assistente.
8. Critérios são carregados integralmente e reinstalação não os sobrescreve.
9. OCR mantém aviso explícito; PDF ilegível é erro, não falso sucesso.
10. Relatório nunca afirma aprovação oficial.

## 13. Verificação final

Comandos e resultados esperados:

```powershell
$env:PYTHONPATH=(Resolve-Path src).Path
python -m unittest discover -s tests -v      # todos PASS; skips só de plataforma, contados
python -m unittest tests.unit.core.test_budget tests.unit.core.test_facts -v
python -m unittest tests.integration.test_enunciados -v
python -m unittest tests.packaging.test_installer -v
```

```sh
bash packaging/linux/build-bundle.sh
bash tests/acceptance/run-offline.sh dist/java-assistente-linux-x86_64
```

- Duas execuções seguidas da mesma fixture: mesmas evidências e mesmos hashes.
- Bundle ≤ 2 GiB; perfil presente e preservado após reinstalação.
- WSL Ubuntu 24.04 é evidência Linux; Linux Mint real em 4–6 GB continua gate pendente e será registrado como não verificado.
- Relatório final com contagem exata de testes, falhas, skips e ambiente.

## 14. Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| Worktree suja confunde revisão | Revisão pega mudança alheia | Inventário, patch e hashes; revisão só dos arquivos da tarefa |
| Refatoração de `session.py` quebra regressões | Perda de comportamento atual | Migração de testes antes da remoção; suíte completa a cada tarefa |
| Truncamento de fonte Java real | Classe incompleta | `output_tokens` 640 + orçamento por seção + teste de limite |
| Extrator continua limitado | Falso "sem contrato" | Mensagem explícita + confirmação do usuário + fixtures variadas |
| Regras genéricas virarem novas heurísticas | Volta do acoplamento | Teste anti-hard-code + regras derivadas de texto verbatim |
| Adaptador abstrato sem segunda linguagem | Interface errada | Stub obrigatório + núcleo sem import de `java_assistant.java` |
| Tempo de inferência no hardware real | Estouro de tempo | Limites no perfil; medição WSL registrada como parcial |

## 15. Limitações registradas (ajuste 6)

- **UML visual não implementado.** OCR extrai texto, mas caixas, compartimentos, conectores e relações espaciais não são interpretados com confiabilidade. Quando a estrutura não vier da camada textual, o assistente declara "estrutura não reconhecida" e pede confirmação — não inventa relação.
- **Testes dos jurados indisponíveis.** Compilação e validação estrutural não provam regra de negócio.
- **Qualidade do modelo real não medida aqui.** Fixtures usam modelo scripted; a evidência com Qwen 3B é a execução WSL/Mint.
- **Estimativa de tokens é heurística.** `chars_per_token` é conservador, não um tokenizador.
- **Segunda linguagem não validada.** Só a interface e o stub existem.
- **Memória `.assistente` adiada.** Retomada entre sessões, diário e reconciliação continuam pendentes.
- **Hardware real pendente.** RAM, tempo de inicialização, USB 2.0 e instruções de CPU só no Linux Mint alvo.

## 16. Critérios de aceitação

1. Perfil global criado uma vez, validado, com override por projeto e preservado na reinstalação.
2. Comandos vêm do perfil; renomear/desabilitar funciona; desconhecido mostra ajuda gerada.
3. `src/` não contém nomes ou regras do fixture.
4. Todos os comportamentos da seção 12 têm teste verde.
5. Sem contrato confiável: pergunta explícita, zero geração, zero compilação, zero mensagem de sucesso.
6. "Solução concluída" só com geração/validação + compilação + execução quando há entrada.
7. Contexto respeita 4096 tokens, com prioridade, truncamento e omissão registrados; critérios grandes falham explicitamente.
8. Os cinco enunciados distintos são gerados, compilados, validados e executados quando aplicável, com Java 8 real.
9. Stub prova que o núcleo não depende de Java.
10. Duas execuções da mesma fixture produzem evidências e hashes idênticos.
11. Suíte completa verde; teste de empacotamento verde; bundle ≤ 2 GiB; aceitação WSL executada.
12. Worktree `opencode` reproduz 24 + 3 arquivos com hashes; checkout original intacto.
13. Memória `.assistente` explicitamente fora desta entrega, registrada como pendência.

## 17. Preparação do perfil de competição

1. Após instalar, editar `~/.config/java-assistente/perfil.json` (ou copiar `share/perfil-padrao.json` do pacote).
2. Ajustar somente o necessário: caminhos do toolchain se o layout do bundle mudar, `libraries`, timeouts, `repair_attempts`, `context_tokens`, `output_tokens` e aliases de comando.
3. Para um exercício específico, criar `<projeto>/.assistente/perfil.json` apenas com as chaves que diferem.
4. Abrir `java-assistente` na pasta do exercício: o perfil é validado antes do primeiro prompt; erro mostra chave, valor e faixa aceita.
5. Conferir com `/perfil` o caminho efetivo, a origem (global ou projeto) e os limites em vigor.
6. Não é necessário editar código, reinstalar ou ter rede.

## 18. Registro dos ajustes aprovados

| Ajuste do parceiro | Onde está atendido |
|---|---|
| 1. Não apagar sem substituição e regressão; heurísticas → regras genéricas | 7.5, 12 |
| 2. Sem contrato confiável falha explícito; nunca compilar antigos e dizer "concluída" | 7.4, 7.9, 16.5–16.6 |
| 3. Orçamento real para 4096 tokens com prioridade e truncamento | 7.6, 16.7 |
| 4. Inventário 24 modificados + 3 não rastreados | 9 |
| 5. Reprodução do estado na worktree com inventário, patch e hashes | 9 |
| 6. UML visual como requisito não implementado | 3, 15 |
| 7. Tarefas derivadas do design, sem teto prévio | 10 |

Decisões do parceiro: arquitetura A; memória `.assistente` na entrega seguinte; perfil global em `~/.config/java-assistente/perfil.json` com override opcional por projeto; somente Java 8 real com adaptador-stub; nenhuma segunda linguagem agora.

## 19. Builder check — decisões de construção

Um leitor independente tentou planejar a partir deste documento e devolveu oito perguntas. Nenhuma ficou pendente para o parceiro humano; todas foram resolvidas aqui como decisões do construtor, com o motivo.

| Pergunta | Decisão | Motivo |
|---|---|---|
| Quem responde pedido livre sem PDF? | Loop de ações existente; solver só com contrato `trusted` | Preserva o comportamento atual (regressão 4) sem fingir validação de contrato |
| Como `Requirement.scope` é derivado? | Seções por cabeçalho igual ao nome da unidade; sem menção → `scope=None` | Determinístico, testável, sem palavra-chave de domínio |
| Quem emite `confidence` e com que escala? | Tabela da seção 7.2; `trusted` exige todas ≥ 0,9 e nenhuma ambiguidade | Fronteira explícita entre `trusted` e `needs_confirmation` |
| Compilar arquivos alheios ao contrato? | Compila todas as fontes; diagnóstico de arquivo alheio interrompe e é reportado, nunca reescrito | Dependências entre arquivos exigem conjunto completo; honestidade impede "consertar" código do usuário |
| Quando validar caminhos do perfil? | Esquema/faixas/aliases na carga; existência ao iniciar, antes do primeiro prompt | Falha cedo, com o caminho nomeado, sem impedir testes que constroem a sessão diretamente |
| O que significa desabilitar comando? | Omitir a chave; `exit` é obrigatório | Saída garantida e validação simples |
| Usar a worktree existente do harness? | Não; criar a nova em `Downloads\java-assistente-offline-opencode` | A existente é limpa, não tem o estado não commitado e pode pertencer a outra sessão |
| Fixtures só de caminho feliz? | Feliz + reparo + negativo em cada uma | Exercita `repair_attempts`, honestidade e limites |

Status histórico em 2026-10-23, quando este design foi escrito: pronto para revisão e aprovação; naquele momento nenhum código, worktree ou commit havia sido criado. O estado atual está no plano de implementação e no código/testes desta worktree.

