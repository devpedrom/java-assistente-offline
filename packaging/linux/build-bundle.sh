#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
ARTIFACTS_DIR=${ARTIFACTS_DIR:-"$PROJECT_ROOT/artifacts/linux-x86_64"}
OUTPUT_DIR=${OUTPUT_DIR:-"$PROJECT_ROOT/dist/java-assistente-linux-x86_64"}

require_path() {
    if [ ! -e "$1" ]; then
        echo "Artefato obrigatório ausente: $1" >&2
        exit 1
    fi
}

require_path "$ARTIFACTS_DIR/llama/llama-server"
require_path "$ARTIFACTS_DIR/model.gguf"
require_path "$ARTIFACTS_DIR/native.tar.gz"

rm -rf -- "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
python3 "$SCRIPT_DIR/assemble_runtime.py" \
    --project-root "$PROJECT_ROOT" \
    --artifacts-dir "$ARTIFACTS_DIR" \
    --output "$OUTPUT_DIR/runtime.tar.gz"
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
