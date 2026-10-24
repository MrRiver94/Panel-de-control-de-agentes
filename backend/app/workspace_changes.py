"""Compare dirty Git files without attributing pre-existing changes to a mission."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import subprocess


def workspace_snapshot(workspace: str) -> dict[str, str]:
    result = subprocess.run(
        ["git", "-c", "status.relativePaths=true", "-C", workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", "."],
        capture_output=True, check=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    entries = iter(result.stdout.split(b"\0"))
    snapshot = {}
    root = Path(workspace).resolve()
    for entry in entries:
        if not entry:
            continue
        status, name = entry[:2], os.fsdecode(entry[3:])
        path = root / name
        if status[:1] in {b"R", b"C"} or status[1:2] in {b"R", b"C"}:
            next(entries, None)  # porcelain -z puts the original path after the destination.
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
