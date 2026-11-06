#!/bin/bash
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export PYTHONPATH="$ROOT/app"
export JAVA_ASSISTANT_HOME="$ROOT"
export PATH="$ROOT/tools/native/bin:$ROOT/tools/jdk/bin:$PATH"
export LD_LIBRARY_PATH="$ROOT/tools/native/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONDONTWRITEBYTECODE=1
python3 -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ necessário"'
cd -- "${JAVA_ASSISTANT_PROJECT:-$ROOT/exercicio-casting}"
exec python3 "$ROOT/portable.py" "$@"
