#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
ARTIFACTS_DIR=${ARTIFACTS_DIR:-"$PROJECT_ROOT/artifacts/linux-x86_64"}
OUTPUT_DIR=${OUTPUT_DIR:-"$PROJECT_ROOT/dist/java-assistente-linux-x86_64"}
STAGING=$(mktemp -d)

cleanup() { rm -rf -- "$STAGING"; }
trap cleanup EXIT HUP INT TERM

require_path() {
    if [ ! -e "$1" ]; then
        echo "Artefato obrigatório ausente: $1" >&2
        exit 1
    fi
}

require_path "$ARTIFACTS_DIR/llama/llama-server"
require_path "$ARTIFACTS_DIR/model.gguf"
require_path "$ARTIFACTS_DIR/jdk"
require_path "$ARTIFACTS_DIR/poppler"
require_path "$ARTIFACTS_DIR/tesseract"

mkdir -p "$STAGING/runtime/bin" "$STAGING/runtime/app" "$STAGING/runtime/share" "$STAGING/runtime/tools"
cp -a "$ARTIFACTS_DIR/jdk" "$STAGING/runtime/tools/jdk"
cp -a "$ARTIFACTS_DIR/poppler" "$STAGING/runtime/tools/poppler"
cp -a "$ARTIFACTS_DIR/tesseract" "$STAGING/runtime/tools/tesseract"
cp -a "$ARTIFACTS_DIR/llama" "$STAGING/runtime/tools/llama"
cp -a "$PROJECT_ROOT/src/java_assistant" "$STAGING/runtime/app/java_assistant"
cp "$PROJECT_ROOT/instructions/CRITERIOS_GERAIS.md" "$STAGING/runtime/share/CRITERIOS_GERAIS.md"
cp "$SCRIPT_DIR/java-assistente" "$STAGING/runtime/bin/java-assistente"
cp "$SCRIPT_DIR/desinstalar.sh" "$STAGING/runtime/bin/desinstalar"
chmod +x "$STAGING/runtime/tools/llama/llama-server" "$STAGING/runtime/bin/java-assistente" "$STAGING/runtime/bin/desinstalar"

rm -rf -- "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
tar -czf "$OUTPUT_DIR/runtime.tar.gz" -C "$STAGING/runtime" .
cp "$ARTIFACTS_DIR/model.gguf" "$OUTPUT_DIR/model.gguf"
cp "$SCRIPT_DIR/instalar.sh" "$OUTPUT_DIR/instalar.sh"
chmod +x "$OUTPUT_DIR/instalar.sh"
(
    cd "$OUTPUT_DIR"
    sha256sum runtime.tar.gz model.gguf > manifest.sha256
)

TOTAL_BYTES=$(du -sb "$OUTPUT_DIR" | awk '{print $1}')
if [ "$TOTAL_BYTES" -gt 2147483648 ]; then
    echo "Bundle excede o limite de 2 GB: $TOTAL_BYTES bytes" >&2
    exit 1
fi
echo "Bundle criado em $OUTPUT_DIR ($TOTAL_BYTES bytes)."
