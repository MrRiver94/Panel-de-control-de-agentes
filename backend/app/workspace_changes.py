"""Compare dirty Git files without attributing pre-existing changes to a mission."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import subprocess
from .git_local import run_git


def workspace_snapshot(workspace: str) -> dict[str, str]:
    prefix = run_git(workspace,'rev-parse','--show-prefix').decode('utf-8').rstrip('\r\n')
    result = run_git(workspace,'status','--porcelain=v1','-z','--untracked-files=all','--','.')
    entries = iter(result.split(b"\0"))
    snapshot = {}
    root = Path(workspace).resolve()
    for entry in entries:
        if not entry:
            continue
        status, name = entry[:2], os.fsdecode(entry[3:])
        if prefix:
            if not name.startswith(prefix): continue
            name = name[len(prefix):]
        path = root / name
        if status[:1] in {b"R", b"C"} or status[1:2] in {b"R", b"C"}:
            original = next(entries, None)
            if original:
                original_name = os.fsdecode(original)
                if prefix and original_name.startswith(prefix):
                    original_name = original_name[len(prefix):]
                original_path = root / original_name
                if original_path.resolve().is_relative_to(root) and not original_path.exists():
                    snapshot[original_name] = 'deleted'
        if not path.resolve().is_relative_to(root):
            continue
        if path.is_symlink():
            digest = sha256(os.fsencode(os.readlink(path))).hexdigest()
        elif path.is_file():
            hasher = sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
        elif not path.exists():
            digest = "deleted"
        else:
            continue
        snapshot[name] = digest
    return snapshot


def changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
