"""Bounded before/after diffs, including files that were dirty before the mission."""
from __future__ import annotations

from difflib import unified_diff
from pathlib import Path
import os
import re
import subprocess

from .workspace_changes import workspace_snapshot, changed_paths
from .git_local import run_git

MAX_FILE_BYTES = 128_000
MAX_PATCH_CHARS = 60_000
MAX_TOTAL_CHARS = 240_000
SENSITIVE_PATH = re.compile(r"(?:^|/)(?:\.env[^/]*|auth\.json|credentials[^/]*|[^/]*\.(?:pem|key|p12)|id_rsa|id_ed25519)$",re.I)
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|(?:api[_-]?key|password|secret|access[_-]?token)\s*['\"]?\s*[:=]\s*['\"][^'\"]+['\"])",re.I)


def git(workspace: str, *args: str) -> bytes:
    return run_git(workspace,*args)


def file_content(workspace: str, name: str) -> bytes | None:
    path=Path(workspace)/name
    if SENSITIVE_PATH.search(name.replace('\\','/')) or not path.resolve().is_relative_to(Path(workspace).resolve()) or path.is_symlink():
        return None
    if not path.exists(): return b''
    if not path.is_file() or path.stat().st_size>MAX_FILE_BYTES: return None
    return path.read_bytes()


def capture_baseline(workspace: str) -> dict:
    fingerprints=workspace_snapshot(workspace)
    blobs={}
    for entry in git(workspace,'ls-files','--stage','-z','--','.').split(b'\0'):
        if not entry: continue
        descriptor,name=entry.split(b'\t',1)
        mode,oid,stage=descriptor.split()
        if stage==b'0' and mode in {b'100644',b'100755'}:
            blobs[os.fsdecode(name)]=oid.decode('ascii')
    return {'fingerprints':fingerprints,'blobs':blobs,
            'dirty':{name:file_content(workspace,name) for name in fingerprints}}


def before_content(workspace: str, baseline: dict, name: str) -> bytes | None:
    if name in baseline['dirty']: return baseline['dirty'][name]
    oid=baseline['blobs'].get(name)
    if not oid: return b''
    if int(git(workspace,'cat-file','-s',oid))>MAX_FILE_BYTES: return None
    return git(workspace,'cat-file','-p',oid)


def collect_diffs(workspace: str, baseline: dict) -> list[dict]:
    paths=changed_paths(baseline['fingerprints'],workspace_snapshot(workspace))
    result=[]; remaining=MAX_TOTAL_CHARS
    for name in paths:
        item={'path':name,'patch':'','binary':False,'truncated':False,'redacted':False}
        if SENSITIVE_PATH.search(name.replace('\\','/')):
            item.update(redacted=True,patch='Contenido sensible oculto por el nombre del archivo.')
        else:
            before,after=before_content(workspace,baseline,name),file_content(workspace,name)
            try:
                if before is None or after is None or b'\0' in before or b'\0' in after: raise UnicodeError()
                original,updated=before.decode('utf-8'),after.decode('utf-8')
                lines=lambda value:[line if line.endswith('\n') else line+'\n' for line in value.splitlines(True)]
                patch=''.join(unified_diff(lines(original),lines(updated),fromfile='antes/'+name,tofile='despues/'+name))
                if not patch and original!=updated:
                    patch='Cambio en finales de línea o formato del archivo.'
                item['redacted']=bool(SECRET.search(patch))
                patch=SECRET.sub('[SECRETO OCULTO]',patch)
                limit=min(MAX_PATCH_CHARS,remaining)
                item.update(patch=patch[:limit],truncated=len(patch)>limit)
                remaining-=min(len(patch),limit)
            except UnicodeError:
                item.update(binary=True,patch='Archivo binario, enlace o contenido demasiado grande para mostrar.')
        result.append(item)
    return result
