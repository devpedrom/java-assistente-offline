"""Assemble the authorized >2 GiB two-model edition from existing local files."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--ollama', type=Path, required=True)
p.add_argument('--exercise', type=Path, required=True)
p.add_argument('--jdk', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[2]
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
shutil.copytree(root/'src', out/'app', ignore=shutil.ignore_patterns('__pycache__'))
shutil.copytree(root/'packaging/linux/portable', out, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
(out/'share').mkdir()
shutil.copy2(root/'instructions/CRITERIOS_GERAIS.md', out/'share')
shutil.copytree(a.jdk, out/'tools/jdk', symlinks=False, ignore=shutil.ignore_patterns('src.zip'))
shutil.copytree(a.ollama/'bin', out/'ollama/bin')
shutil.copytree(a.ollama/'lib/ollama', out/'ollama/lib/ollama', symlinks=True,
                ignore=shutil.ignore_patterns('cuda*', 'vulkan'))
shutil.copytree(a.ollama/'models', out/'ollama/models')
for folder in ('exercicio-casting', 'referencia-casting', 'tools/native/bin', 'tools/native/lib'):
    (out/folder).mkdir(parents=True, exist_ok=True)
for source in a.exercise.iterdir():
    if source.suffix.lower() in ('.pdf', '.class'):
        shutil.copy2(source, out/'referencia-casting'/source.name)
        # GUI entry point is reference material, not an executable judge.
        if source.name != 'Principal.class':
            shutil.copy2(source, out/'exercicio-casting'/source.name)
for name in ('pdftotext', 'pdftoppm', 'pdfimages'):
    shutil.copy2(shutil.which(name), out/'tools/native/bin'/name)
# Bundle transitive libraries reported by ldd; keep the host's matched glibc.
executables = [*(out/'tools/native/bin').iterdir(), *(out/'tools/jdk/bin').iterdir(),
               *(out/'ollama/lib/ollama').glob('*.so*'), out/'ollama/bin/ollama']
for binary in executables:
    result = subprocess.run(['ldd', str(binary)], capture_output=True, text=True)
    for match in re.finditer(r'=> (/[^\n]+?)\s+\(0x', result.stdout):
        source = Path(match.group(1))
        if source.name.startswith(('libc.so', 'libm.so', 'libpthread.so', 'libdl.so', 'librt.so')):
            continue
        target = out/'tools/native/lib'/source.name
        if not target.exists():
            shutil.copy2(source, target)
profile = json.loads((root/'packaging/linux/perfil-padrao.json').read_text())
profile['toolchain'] = {key: f'tools/jdk/bin/{name}' for key, name in
                       [('compiler', 'javac'), ('runtime', 'java'), ('inspector', 'javap')]}
profile['limits'].update(repair_attempts=5, context_tokens=8192, output_tokens=2048, compile_timeout_s=60)
profile['context']['sections'].update(protocol=400, criteria=600, spec_target=1200, parents=1400,
                                      pdf_excerpt=600, rules=500, memory=150, user_request=1000)
(out/'share/perfil-padrao.json').write_text(json.dumps(profile, indent=2))
(out/'config.json').write_text(json.dumps({'models': ['qwen2.5-coder:1.5b', 'phi3:latest'], 'context_length': 16384}, indent=2))
(out/'iniciar.sh').chmod(0o755)
with (out/'manifest.sha256').open('w') as manifest:
    for source in sorted(out.rglob('*')):
        if source.is_file() and source.name != 'manifest.sha256':
            with source.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            manifest.write(f'{digest}  {source.relative_to(out)}\n')
print(out)
print('Bytes:', sum(f.stat().st_size for f in out.rglob('*') if f.is_file()))
