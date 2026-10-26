"""Exercise the packaged runtime from another directory without Python/Node in PATH."""
from pathlib import Path
import os
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory

executable = Path(sys.argv[1]).resolve(strict=True)
with TemporaryDirectory(prefix='slimeops-portable-check-') as temporary:
    directory = Path(temporary)
    environment = os.environ.copy()
    for name in ('PYTHONHOME', 'PYTHONPATH', 'TCL_LIBRARY', 'TK_LIBRARY', 'VIRTUAL_ENV'):
        environment.pop(name, None)
    environment['PATH'] = str(Path(environment.get('SystemRoot', 'C:/Windows')) / 'System32')
    environment['CODEX_HOME'] = str(directory / 'absent-provider')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    result = subprocess.run(
        [str(executable), '--smoke-test', '--headless', '--no-browser', '--port', str(port),
         '--data-dir', str(directory / 'personal')], cwd=directory, env=environment, timeout=40,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
    )
    log = directory / 'personal' / 'slimeops.log'
    if result.returncode:
        if log.exists():
            print(log.read_text(encoding='utf-8'))
        raise SystemExit(f'El ejecutable fallo la comprobacion portatil: {result.returncode}')
    if not log.exists() or 'Application shutdown complete' not in log.read_text(encoding='utf-8'):
        raise SystemExit('No se pudo confirmar el cierre ordenado del ejecutable.')
    print('Ejecutable verificado sin Python/Node en PATH y desde otra carpeta.')
