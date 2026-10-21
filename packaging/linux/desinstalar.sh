#!/bin/sh
set -eu

DATA_ROOT=${XDG_DATA_HOME:-"$HOME/.local/share"}
APP_DATA="$DATA_ROOT/java-assistente"
USER_COMMAND="$HOME/.local/bin/java-assistente"

rm -rf -- "$APP_DATA"
rm -f -- "$USER_COMMAND"
echo "Aplicativo removido. Critérios e memória foram preservados."
