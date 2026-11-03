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
FIRST_STATUS=0
FIRST_OUTPUT=$(printf '/sair\n' | timeout 300 "$WORK/origem/instalar.sh") || FIRST_STATUS=$?
if [ "$FIRST_STATUS" -ne 0 ]; then
    printf '%s\n' "$FIRST_OUTPUT" >&2
    echo "FALHA: instalador terminou com código $FIRST_STATUS." >&2
    exit 1
fi
printf '%s\n' "$FIRST_OUTPUT"
case "$FIRST_OUTPUT" in
    *"projeto: $WORK/Projeto com acento á"*) ;;
    *)
        echo "FALHA: instalador não abriu na pasta atual da solução." >&2
        exit 1
        ;;
esac

PROFILE="$XDG_CONFIG_HOME/java-assistente/perfil.json"
if [ ! -f "$PROFILE" ]; then
    echo "FALHA: perfil padrão não foi instalado em $PROFILE." >&2
    exit 1
fi
sed -i 's/"repair_attempts": 2/"repair_attempts": 1/' "$PROFILE"
if ! grep -q '"repair_attempts": 1' "$PROFILE"; then
    echo "FALHA: padrão de edição não encontrado em $PROFILE." >&2
    exit 1
fi
JAVA_ASSISTANT_NO_START=1 timeout 300 "$WORK/origem/instalar.sh" >/dev/null
if ! grep -q '"repair_attempts": 1' "$PROFILE"; then
    echo "FALHA: reinstalação sobrescreveu o perfil editado." >&2
    exit 1
fi

mv "$WORK/origem" "$WORK/origem-removida"

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
