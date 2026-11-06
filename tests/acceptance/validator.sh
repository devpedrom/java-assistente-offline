#!/bin/sh
set -eu
[ "$#" -eq 1 ] || { echo "uso: $0 pasta-da-solucao" >&2; exit 2; }
SOL=$(CDPATH= cd -- "$1" && pwd)
FIX=$(CDPATH= cd -- "$(dirname -- "$0")/../fixtures/frota" && pwd)
OUT=$(mktemp -d)
trap 'rm -rf -- "$OUT"' EXIT HUP INT TERM
timeout 60 javac -encoding UTF-8 --release 8 -d "$OUT" "$SOL"/*.java
timeout 60 java -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8 -Dstderr.encoding=UTF-8 -cp "$FIX:$OUT" Frota --console > "$OUT/resultado.txt" 2>&1 || {
    cat "$OUT/resultado.txt"
    exit 1
}
cat "$OUT/resultado.txt"
python3 "$(dirname -- "$0")/../qualidade/validator.py" "$OUT/resultado.txt"
