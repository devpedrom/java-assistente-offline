#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 /caminho/java-assistente-linux-x86_64" >&2
    exit 2
fi

BUNDLE=$(CDPATH= cd -- "$1" && pwd)
WORK=$(mktemp -d)
cleanup() { rm -rf -- "$WORK"; }
trap cleanup EXIT HUP INT TERM

export HOME="$WORK/home"
export XDG_DATA_HOME="$WORK/data"
export XDG_CONFIG_HOME="$WORK/config"
export XDG_STATE_HOME="$WORK/state"
mkdir -p "$HOME" "$WORK/Projeto com acento á" "$WORK/origem"
cp -a "$BUNDLE/." "$WORK/origem/"

START=$(date +%s)
cd "$WORK/Projeto com acento á"
FIRST_OUTPUT=$(printf '/enunciado\nclass Conta\n+ total(): int\n/fim\n/sair\n' | timeout 300 "$WORK/origem/instalar.sh")
printf '%s\n' "$FIRST_OUTPUT"
case "$FIRST_OUTPUT" in
    *"projeto: $WORK/Projeto com acento á"*) ;;
    *)
        echo "FALHA: instalador não abriu na pasta atual da solução." >&2
        exit 1
        ;;
esac
mv "$WORK/origem" "$WORK/origem-removida"

SECOND_OUTPUT=$(printf '/contrato\n/estado\n/sair\n' | timeout 300 "$HOME/.local/bin/java-assistente")
printf '%s\n' "$SECOND_OUTPUT"
case "$SECOND_OUTPUT" in
    *"Projeto retomado"*"Conta"*"Próxima ação"*) ;;
    *) echo "FALHA: segunda sessão não retomou o contrato." >&2; exit 1 ;;
esac
test -s .assistente/projeto.json
test -s .assistente/requisitos.json
END=$(date +%s)

ELAPSED=$((END - START))
if [ "$ELAPSED" -gt 300 ]; then
    echo "FALHA: instalação e primeiro prompt excederam 5 minutos ($ELAPSED s)." >&2
    exit 1
fi
if find . -name '*.class' -print -quit | grep -q .; then
    echo "FALHA: classes compiladas ficaram na pasta de entrega." >&2
    exit 1
fi

echo "PASS: inicialização offline após remover a origem em $ELAPSED s."
echo "PASS: contrato retomado em dois processos sem reenviar o enunciado."
echo "Execute os demais itens de tests/acceptance/checklist.md neste mesmo hardware."
