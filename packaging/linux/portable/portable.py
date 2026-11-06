"""Local portable entry point with alternating repair models."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time
from urllib.request import urlopen
from java_assistant.cli import run_cli
from java_assistant.config import AppConfig
from java_assistant.java.toolchain import JavaToolchain
from java_assistant.model.client import LocalHttpTransport, ModelClient
from java_assistant.pdf.extract import PdfExtractor
from java_assistant.profile import load_profile
from java_assistant.session import AssistantSession


class AlternatingModel:
    def __init__(self, port, output_tokens, models, announce=print):
        self.transport = LocalHttpTransport(port, max_tokens=output_tokens)
        self.models, self.announce, self.attempts = models, announce, {}

    def complete(self, messages):
        text = '\n'.join(m.content for m in messages if m.role == 'user')
        target = re.search(r'Escreva SOMENTE (\w+)\.java', text)
        repair = 'ERRO DA VERIFICAÇÃO ANTERIOR:' in text or 'resposta anterior foi rejeitada' in text
        key = target.group(1) if target else 'chat'
        attempt = self.attempts.get(key, 0) + 1 if repair else 0
        self.attempts[key] = attempt
        model = self.models[attempt % len(self.models)]
        self.announce(f'[modelo: {model}; unidade: {key}; tentativa: {attempt + 1}]')
        return ModelClient(lambda payload: self.transport(dict(payload, model=model, stream=False))).complete(messages)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resolver', action='store_true')
    parser.add_argument('--diagnostico', action='store_true')
    args = parser.parse_args()
    home = Path(__file__).resolve().parent
    settings = json.loads((home/'config.json').read_text())
    for variable, leaf in [('XDG_DATA_HOME', 'data'), ('XDG_CONFIG_HOME', 'config'), ('XDG_STATE_HOME', 'state')]:
        os.environ[variable] = str(home/'dados'/leaf)
    config = AppConfig.load(Path.cwd())
    config.config_dir.mkdir(parents=True, exist_ok=True)
    profile_path = config.config_dir/'perfil.json'
    if not profile_path.exists():
        profile_path.write_bytes((home/'share/perfil-padrao.json').read_bytes())
    profile = load_profile(config, app_home=home, available_adapters=('java8',))
    tools = home/'tools/native/bin'
    for executable in [*profile.toolchain.values(), tools/'pdftotext']:
        result = subprocess.run([str(executable), '-version' if executable.name != 'pdftotext' else '-v'], capture_output=True, timeout=20)
        if result.returncode:
            raise RuntimeError(f'Ferramenta incompatível: {executable.name}: {result.stderr.decode(errors="replace")}')
    if args.diagnostico:
        print('Java/PDF executáveis. Modelos configurados:', ', '.join(settings['models']))
        print('OCR não incluído. Inferência e RAM não avaliadas neste diagnóstico.')
        return 0
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, OLLAMA_HOST=f'127.0.0.1:{port}', OLLAMA_MODELS=str(home/'ollama/models'),
               OLLAMA_CONTEXT_LENGTH=str(settings['context_length']), OLLAMA_MAX_LOADED_MODELS='1',
               OLLAMA_NUM_PARALLEL='1', OLLAMA_NO_CLOUD='1', CUDA_VISIBLE_DEVICES='-1',
               HOME=str(home/'dados'), OLLAMA_KEEP_ALIVE='5m')
    session = None
    logdir = home/'dados/logs'
    logdir.mkdir(parents=True, exist_ok=True)
    with (logdir/'servidor.log').open('w') as log:
        server = subprocess.Popen([str(home/'ollama/bin/ollama'), 'serve'], env=env,
                                  stdout=log, stderr=log, start_new_session=True)
        try:
            for _ in range(120):
                if server.poll() is not None:
                    raise RuntimeError('Servidor encerrou; veja dados/logs/servidor.log')
                try:
                    with urlopen(f'http://127.0.0.1:{port}/api/tags', timeout=1) as response:
                        available = {item['name'] for item in json.load(response)['models']}
                    break
                except OSError:
                    time.sleep(0.25)
            else:
                raise RuntimeError('Servidor não iniciou em 30 segundos')
            if not set(settings['models']) <= available:
                raise RuntimeError('Modelos locais ausentes; copie a pasta inteira novamente')
            session = AssistantSession(
                config=config, profile=profile,
                model=AlternatingModel(port, profile.limits.output_tokens, settings['models']),
                pdf_extractor=PdfExtractor(pdftotext=tools/'pdftotext', pdftoppm=tools/'pdftoppm',
                                          pdfimages=tools/'pdfimages', tesseract=tools/'tesseract'),
                toolchain=JavaToolchain(config.project_root, javac=profile.toolchain['compiler'],
                                       java=profile.toolchain['runtime'], javap=profile.toolchain['inspector']),
                criteria_template=home/'share/CRITERIOS_GERAIS.md')
            if args.resolver:
                if len(list(Path.cwd().glob('*.pdf'))) != 1:
                    raise RuntimeError('Modo automático exige exatamente um PDF; use o chat para escolher')
                for command in ('/pdf', '1', 'Resolva o exercício completo', '/relatorio'):
                    reply = session.handle(command)
                    print(reply.text, flush=True)
                    if command.startswith('Resolva'):
                        completed = reply.text.startswith('Solução concluída')
                return 0 if completed else 1
            return run_cli(config, session=session)
        finally:
            if session:
                session.close()
            if server.poll() is None:
                os.killpg(server.pid, signal.SIGTERM)
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(server.pid, signal.SIGKILL)
                    server.wait()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f'Não foi possível executar: {error}')
        raise SystemExit(2)
