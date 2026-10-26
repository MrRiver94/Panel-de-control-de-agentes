"""Collect redistribution notices from the explicitly locked build environment."""
from importlib import metadata
import json
from pathlib import Path
import re
import shutil
import sys

root = Path(__file__).resolve().parents[1]
output = root / '.build' / 'notices'
licenses = output / 'licenses'
licenses.mkdir(parents=True, exist_ok=True)
components = []
for filename, role in [('requirements.lock.txt', 'runtime'), ('requirements-build.txt', 'build')]:
    for line in (root / 'backend' / filename).read_text(encoding='utf-8').splitlines():
        match = re.match(r'([\w.-]+)==', line)
        if not match:
            continue
        name = match[1]
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue  # Platform-specific build dependency.
        component = {'name': name, 'version': distribution.version, 'role': role, 'notices': []}
        for item in distribution.files or []:
            if not re.search(r'(^|/)(license[^/]*|copying[^/]*|notice[^/]*)$', str(item), re.I):
                continue
            source = Path(distribution.locate_file(item))
            if not source.is_file():
                continue
            relative = Path(str(item))
            if relative.is_absolute() or '..' in relative.parts:
                continue
            destination = licenses / name / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            component['notices'].append(destination.relative_to(output).as_posix())
        components.append(component)

for name, candidates in {
    'CPython': [Path(sys.base_prefix) / 'LICENSE.txt'],
    'Tcl': [Path(sys.base_prefix) / 'tcl' / 'tcl8.6' / 'license.terms', root / 'packaging' / 'licenses' / 'Tcl.txt'],
    'Tk': [Path(sys.base_prefix) / 'tcl' / 'tk8.6' / 'license.terms'],
}.items():
    found = next((path for path in candidates if path.is_file()), None)
    if not found:
        raise SystemExit(f'Falta la licencia de {name}; revisa la instalación de Python antes de distribuir.')
    destination = licenses / name / found.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(found, destination)
    components.append({'name': name, 'version': sys.version.split()[0] if name == 'CPython' else '8.6',
                       'role': 'runtime', 'notices': [destination.relative_to(output).as_posix()]})

(output / 'components.json').write_text(json.dumps(components, indent=2) + '\n', encoding='utf-8')
