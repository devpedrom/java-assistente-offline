# Assistente Java — edição portátil de dois modelos

Pacote privado para Linux Mint **22.x x86-64**, CPU, Python 3.10+ do sistema.
Os binários foram copiados de Mint 22.2 (glibc 2.39); Mint 21 e outros sistemas
não foram certificados. Copie a pasta inteira para o disco local antes de usar.
Não requer sudo, downloads, conta, API remota ou pendrive conectado.
Esta edição excede 2 GiB com autorização do usuário; não altera o bundle padrão.

## Iniciar

Abra um terminal na pasta do pacote:

```bash
bash iniciar.sh --diagnostico
bash iniciar.sh
```

No chat: `/pdf`, escolha `1`, depois `Resolva o exercício completo`.
Ou execute `bash iniciar.sh --resolver` para selecionar o único PDF e gerar.
Os fontes são escritos em `exercicio-casting/`. Arquivos existentes podem ser
atualizados; faça uma cópia se quiser preservar uma solução anterior.
`/relatorio` mostra evidências, `/desfazer` desfaz e `/sair` encerra.
Se receber o arquivo `.tar.gz`, extraia no disco local pelo gerenciador de
arquivos antes de iniciar. O arquivo compactado preserva permissões e links
mesmo quando transportado em pendrive FAT/exFAT.

## Modelos cooperando

Qwen2.5-Coder 1.5B inicia cada unidade. Quando o controlador rejeita a resposta
ou solicita reparo, a unidade alterna entre Phi3 e Qwen. As demais unidades não
são regeneradas por causa da troca. Há até cinco reparos de compilação e cinco
de estrutura; o controlador pode parar antes por resposta inválida.
Só um modelo fica carregado por vez. Isso reduz RAM, mas trocar modelos custa
tempo. A escolha aparece no terminal. Nenhum modelo executa shell.
Cooperação não garante correção nem maior velocidade em todo exercício.

## Casting e outros PDFs

`exercicio-casting/` contém o PDF e as APIs compiladas de referência.
`referencia-casting/` preserva também Principal.class, cuja interface gráfica
não é tratada como juiz automático. Regras do exercício não estão no produto.
Para outro exercício, crie uma pasta com o PDF e execute:

```bash
JAVA_ASSISTANT_PROJECT="/caminho/da/pasta" bash iniciar.sh
```

O pacote inclui Ollama CPU, os dois modelos, JDK e Poppler com bibliotecas.
**OCR não incluído:** Tesseract não estava disponível localmente. O Casting tem
camada de texto; PDFs escaneados podem falhar. Python vem do Linux Mint.
Reserve pelo menos 5 GB de disco; 8 GB de RAM são recomendados para este perfil
de contexto 16384. O funcionamento com 4–6 GB deve ser medido no computador alvo.

## Configuração e diagnóstico

`config.json`: ordem dos modelos e contexto do servidor.
Após a primeira abertura: `dados/config/java-assistente/perfil.json` contém
limites; `CRITERIOS_GERAIS.md` na mesma pasta é editável e preservado.
`dados/logs/servidor.log`: falhas do servidor. Não publique a pasta dados.
O servidor usa porta loopback própria e encerra ao fechar o assistente.
Não edite configurações durante uma geração.
Para conferir a cópia original: `sha256sum -c manifest.sha256`.
Fontes e configurações modificados depois da cópia podem divergir do manifesto.

Compilação e contrato não comprovam regras de negócio. Confira especialmente
pontuação exata das mensagens e todas as ramificações dos salários. Não há
testes oficiais dos jurados incluídos nem certificação de hardware/USB.
