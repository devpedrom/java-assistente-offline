# Correção por método — complemento ao plano de fidelidade

## Objetivo e limite

Corrigir uma classe existente sem pedir ao modelo que a reescreva inteira.
Manter o modelo e os binários locais, operação offline, Java 8 e a raiz de
escrita imutável. Não incorporar nomes ou fórmulas do exercício ao produto.

## Abordagens

- **Classe inteira:** já testada; repetiu os mesmos três erros no desafio.
- **Por método:** escolhida pelo usuário. Contexto menor, membros preservados e
  diagnóstico específico; ainda depende da correção semântica do modelo.
- **Solução manual:** não escolhida; não comprovaria a capacidade do assistente.

## Decisões propostas

1. Usar a API de análise sintática do JDK empacotado para localizar corpos de
   métodos com segurança, em vez de expressões regulares sobre Java arbitrário.
   O pequeno auxiliar confiável roda somente por ação do controlador.
2. Em correções de classe, preservar construtores, atributos e assinaturas.
   Corrigir métodos declarados um por vez; um pedido explicitamente restrito a
   um método não altera os demais. A geração inicial permanece como está.
3. Pedir somente o bloco Java do corpo, fornecendo assinatura, regras relevantes,
   corpo atual, dependências necessárias e diagnóstico. Não dar shell ao modelo.
4. Montar a alteração em cópia temporária e conferir com o analisador que ela
   continua inteiramente dentro do método selecionado. Compilar para Java 8 e
   validar o contrato antes de substituir o arquivo real.
5. Conferir que o fonte real não mudou durante a validação; gravar pelo histórico
   reversível existente. Erro de análise, compilação ou conflito preserva o fonte.
6. Executar testes de comportamento depois das alterações. Casos inferidos seguem
   identificados como inferências; o validador fornecido é uma prova separada.

## Verificação

- Regressões para alteração exclusiva de corpo, sobrecargas, comentários/strings,
  tentativa de injetar outro membro, Java inválido e edição externa concorrente.
- Demonstrar que atributos, construtor e arquivos não solicitados permanecem iguais.
- Retestar os três casos reprovados e a bateria real completa, sem editar a solução
  à mão; depois suíte completa, pacote e aceitação WSL.
- Linux Mint real e testes secretos continuam sem garantia.

Sem instalação, troca de modelo, commit ou publicação implícita.
