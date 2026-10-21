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
export JAVA_ASSISTANT_NO_START=1
mkdir -p "$HOME" "$WORK/Projeto com acento á" "$WORK/origem"
cp -a "$BUNDLE/." "$WORK/origem/"

START=$(date +%s)
"$WORK/origem/instalar.sh"
mv "$WORK/origem" "$WORK/origem-removida"

cd "$WORK/Projeto com acento á"
printf '/sair\n' | timeout 300 "$HOME/.local/bin/java-assistente"
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
echo "Execute os demais itens de tests/acceptance/checklist.md neste mesmo hardware."
