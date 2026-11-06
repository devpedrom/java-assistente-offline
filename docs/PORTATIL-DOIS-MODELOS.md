# Edição portátil local — 2026-11-04

O usuário autorizou uma edição acima de 2 GiB com os modelos locais Qwen2.5-Coder
1.5B e Phi3. O bundle padrão e seu limite não foram alterados.

Montagem reproduzível, somente a partir de arquivos já presentes:

```bash
python3 packaging/linux/build-portable.py --ollama /pasta/ollama_completo \
  --exercise /pasta/casting --jdk /usr/lib/jvm/java-21-openjdk-amd64 \
  --output /pasta/nova/Assistente-Java-Portatil
```

O destino deve ser novo. Usa Python 3.12 para montagem (hashlib.file_digest);
execução requer Python 3.10+. Binários locais desta entrega: Mint 22.2 x86-64,
compatibilidade alvo Mint 22.x. Não houve download/instalação de dependências.
Tesseract indisponível: OCR não faz parte desta edição.

`portable/portable.py` inicia Ollama privado em loopback e usa a sessão existente.
Qwen inicia cada unidade; rejeições/reparos alternam Phi3 e Qwen na mesma unidade.
Um modelo residente, cinco reparos, contexto do servidor 16384, orçamento do
controlador 8192 e saída 2048. A política não avalia semanticamente cada resposta.
`Principal.class` fica apenas na referência, por ser entrada gráfica, não juiz.

Verificações locais em Linux Mint 22.2:
- `bash iniciar.sh --diagnostico`: Java/Poppler executados com sucesso.
- `bash iniciar.sh --resolver`: exit 0; cinco fontes gerados e compilados;
  Biblioteca utilizou Qwen → Phi3 → Qwen. Estrutura aprovada, sem juiz oficial.
- `PYTHONPATH=src python3 -m unittest tests.packaging.test_portable tests.packaging.test_installer -v`:
  cinco testes aprovados, zero falhas/pulos.
- Build tradicional executado, bloqueado pelos artefatos ausentes em artifacts/.
- Aceitação tradicional executada, falhou porque espera instalar.sh, não o
  layout portátil. Isso não é um resultado de aceitação aprovado.

Pendente: outro PC, Mint anterior, hardware 4–6 GB, tempo USB, pico de RAM e
testes completos das regras do Casting. Há divergência de pontuação na mensagem
de Atendente gerada; compilação não prova fidelidade do texto ao enunciado.
