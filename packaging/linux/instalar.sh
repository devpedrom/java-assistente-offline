#!/bin/sh
set -eu

ORIGINAL_DIR=$(pwd -P)
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DATA_ROOT=${XDG_DATA_HOME:-"$HOME/.local/share"}
CONFIG_ROOT=${XDG_CONFIG_HOME:-"$HOME/.config"}
STATE_ROOT=${XDG_STATE_HOME:-"$HOME/.local/state"}
APP_DATA="$DATA_ROOT/java-assistente"
APP_CONFIG="$CONFIG_ROOT/java-assistente"
APP_STATE="$STATE_ROOT/java-assistente"
USER_BIN="$HOME/.local/bin"

cd "$SOURCE_DIR"
sha256sum -c manifest.sha256

RELEASE_ID=$(sha256sum manifest.sha256 | awk '{print substr($1,1,16)}')
RELEASES="$APP_DATA/releases"
RELEASE="$RELEASES/$RELEASE_ID"
STAGING=""

cleanup() {
    if [ -n "$STAGING" ] && [ -d "$STAGING" ]; then
        rm -rf -- "$STAGING"
    fi
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$RELEASES" "$APP_CONFIG" "$APP_STATE" "$USER_BIN"
if [ ! -d "$RELEASE" ]; then
    STAGING=$(mktemp -d "$APP_DATA/.install.XXXXXX")
    tar -xzf runtime.tar.gz -C "$STAGING"
    mkdir -p "$STAGING/model"
    cp model.gguf "$STAGING/model/model.gguf"
    chmod +x "$STAGING/bin/java-assistente"
    mv "$STAGING" "$RELEASE"
    STAGING=""
fi

ln -sfn "$RELEASE" "$APP_DATA/current.new"
mv -Tf "$APP_DATA/current.new" "$APP_DATA/current"

if [ ! -f "$APP_CONFIG/CRITERIOS_GERAIS.md" ]; then
    cp "$RELEASE/share/CRITERIOS_GERAIS.md" "$APP_CONFIG/CRITERIOS_GERAIS.md"
fi

if [ ! -f "$APP_CONFIG/perfil.json" ]; then
    cp "$RELEASE/share/perfil-padrao.json" "$APP_CONFIG/perfil.json"
fi

cat > "$USER_BIN/java-assistente" <<'LAUNCHER'
#!/bin/sh
set -eu
DATA_ROOT=${XDG_DATA_HOME:-"$HOME/.local/share"}
APP_HOME="$DATA_ROOT/java-assistente/current"
export JAVA_ASSISTANT_HOME="$APP_HOME"
exec "$APP_HOME/bin/java-assistente" "$@"
LAUNCHER
chmod +x "$USER_BIN/java-assistente"

cd "$ORIGINAL_DIR"
echo "Instalação concluída. Comando: $USER_BIN/java-assistente"
if [ "${JAVA_ASSISTANT_NO_START:-0}" != "1" ]; then
    exec "$USER_BIN/java-assistente"
fi
