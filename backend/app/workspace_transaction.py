"""Run agents in a private Git baseline and publish with optimistic conflict checks."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4
import os
import shutil
import stat
import subprocess
import sys
import tempfile

from .config import DATA_DIRECTORY
from .git_local import git_environment


class WorkspaceTransactionError(RuntimeError):
    """The workspace cannot be prepared or published safely."""


class WorkspaceConflictError(WorkspaceTransactionError):
    """The original changed; retain the isolated workspace for recovery."""


@dataclass(frozen=True)
class FileState:
    digest: str
    mode: int


@dataclass(frozen=True)
class WorkspaceState:
    head: str | None
    index: dict[str, tuple[str, str]]
    files: dict[str, FileState | None]


class WorkspaceTransaction:
    def __init__(self, workspace: str | Path, storage_root: str | Path | None = None) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self.storage_root = Path(storage_root or DATA_DIRECTORY / 'workspaces').expanduser().resolve()
        self.identifier = uuid4().hex
        self.directory = self.storage_root / self.identifier
        self.repository = self.directory / 'repository'
        self.sandbox = self.repository
        self._source_root = self.workspace
        self._baseline: WorkspaceState | None = None
        self._context_baseline: WorkspaceState | None = None
        self._exclude_path: Path | None = None
        self._exclude_content: bytes | None = None
        self._global_excludes_signature: tuple[str | None, str | None, str | None] = (None, None, None)
        self._prepared = False
        self._published = False
        self._changes: list[str] = []
        self._temporary_paths: set[Path] = set()

    @property
    def recovery_path(self) -> str | None:
        return str(self.sandbox) if self.sandbox.is_dir() else None

    def _git(self, root: Path, *arguments: str, allow_unborn: bool = False) -> bytes:
        try:
            result = subprocess.run(
                ['git', '-C', str(root), *arguments], capture_output=True, timeout=30,
                env=git_environment(), creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise WorkspaceTransactionError('No se pudo consultar Git al preparar el proyecto aislado.') from error
        if allow_unborn and result.returncode == 1:
            return b''
        if result.returncode:
            raise WorkspaceTransactionError('No se pudo consultar el Git del proyecto aislado; revisa su propiedad y permisos.')
        return result.stdout

    @staticmethod
    def _path(root: Path, name: str) -> Path:
        parts = PurePosixPath(name).parts
        if (not parts or PurePosixPath(name).is_absolute() or PureWindowsPath(name).drive
                or '\\' in name or any(part in {'.', '..'} or part.casefold() == '.git' for part in parts)):
            raise WorkspaceTransactionError('El proyecto contiene una ruta que no se puede aislar con seguridad.')
        path = root
        for part in parts:
            path = path / part
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise WorkspaceTransactionError('El aislamiento no admite enlaces simbólicos ni junctions en los archivos del proyecto.')
        if not path.resolve().is_relative_to(root):
            raise WorkspaceTransactionError('Una ruta del proyecto sale del directorio permitido.')
        return path

    def _file(self, root: Path, name: str) -> FileState | None:
        path = self._path(root, name)
        try:
            metadata = path.stat()
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(metadata.st_mode):
            raise WorkspaceTransactionError('El aislamiento solo admite archivos regulares; no admite repositorios anidados ni submódulos.')
        digest = sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(chunk)
        return FileState(digest.hexdigest(), stat.S_IMODE(metadata.st_mode))

    def _excluded(self, root: Path, name: str) -> bool:
        if root not in {self.workspace, self._source_root}:
            return False
        if root / name in self._temporary_paths:
            return True
        # The transaction may be stored under an otherwise unignored source tree.
        return (root / name).is_relative_to(self.directory)

    def _capture(self, root: Path, extra_names: list[str] | None = None) -> WorkspaceState:
        index: dict[str, tuple[str, str]] = {}
        names: set[str] = set()
        for record in self._git(root, 'ls-files', '--stage', '-z', '--', '.').split(b'\0'):
            if not record:
                continue
            descriptor, raw_name = record.split(b'\t', 1)
            mode, oid, stage = descriptor.decode('ascii').split()
            name = os.fsdecode(raw_name)
            if self._excluded(root, name):
                continue
            if stage != '0':
                raise WorkspaceTransactionError('Resuelve los conflictos Git del proyecto antes de iniciar una misión.')
            if mode not in {'100644', '100755'}:
                raise WorkspaceTransactionError('El aislamiento no admite enlaces simbólicos ni submódulos Git.')
            index[name] = (mode, oid)
            names.add(name)
        for raw_name in self._git(root, 'ls-files', '--others', '--exclude-standard', '-z', '--', '.').split(b'\0'):
            if raw_name:
                name = os.fsdecode(raw_name)
                if not self._excluded(root, name):
                    names.add(name)
        if root == self.workspace and self._baseline is not None:
            names.update(self._baseline.files)
        if root == self._source_root and self._context_baseline is not None:
            names.update(self._context_baseline.files)
        names.update(extra_names or [])
        files = {name: self._file(root, name) for name in sorted(names)}
        head = self._git(root, 'rev-parse', '--verify', '--quiet', 'HEAD', allow_unborn=True).decode('ascii').strip() or None
        return WorkspaceState(head, index, files)

    def _check_original(self) -> None:
        if (self._capture(self._source_root) != self._context_baseline
                or self._read_exclude() != self._exclude_content
                or self._read_global_excludes()[0] != self._global_excludes_signature):
            raise WorkspaceConflictError('El proyecto original cambió durante la misión. No se han publicado los cambios; conserva la copia de recuperación.')

    def _read_exclude(self) -> bytes | None:
        if self._exclude_path is None or not self._exclude_path.exists():
            return None
        return self._exclude_path.read_bytes()

    def _read_global_excludes(self) -> tuple[tuple[str | None, str | None, str | None], bytes | None]:
        raw = self._git(self._source_root, 'config', '--path', '--get', 'core.excludesFile', allow_unborn=True)
        if not raw:
            return (None, None, None), None
        configured = raw.decode('utf-8').rstrip('\r\n')
        if not configured:
            return ('', None, None), b''
        path = Path(configured).expanduser()
        # Git interprets relative excludes paths at the repository root, also for -C subdir.
        if not path.is_absolute():
            path = self._source_root / path
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            content = None
        digest = sha256(content).hexdigest() if content is not None else None
        return (configured, str(path.resolve()), digest), content

    def prepare(self) -> str:
        if self._baseline is not None:
            if not self._prepared:
                raise WorkspaceTransactionError('La preparación anterior falló; conserva la copia de recuperación.')
            return str(self.sandbox)
        self._source_root = Path(self._git(self.workspace, 'rev-parse', '--show-toplevel').decode('utf-8').strip()).resolve()
        prefix = self.workspace.relative_to(self._source_root)
        self.sandbox = self.repository / prefix
        context_baseline = self._capture(self._source_root)
        baseline = context_baseline if self.workspace == self._source_root else self._capture(self.workspace)
        exclude_name = self._git(self._source_root, 'rev-parse', '--git-path', 'info/exclude').decode('utf-8').strip()
        self._exclude_path = (self._source_root / exclude_name).resolve()
        self._exclude_content = self._read_exclude()
        self._global_excludes_signature, global_excludes_content = self._read_global_excludes()
        self.repository.mkdir(parents=True, exist_ok=False)
        self.sandbox.mkdir(parents=True, exist_ok=True)
        self._baseline = baseline
        self._context_baseline = context_baseline
        for name, entry in context_baseline.files.items():
            if entry is None:
                continue
            source, target = self._path(self._source_root, name), self._path(self.repository, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        self._git(self.repository, 'init', '-q')
        isolated_exclude = self.repository / '.git' / 'info' / 'exclude'
        isolated_exclude.parent.mkdir(parents=True, exist_ok=True)
        isolated_exclude.write_bytes(self._exclude_content or b'')
        if self._global_excludes_signature[0] is not None:
            frozen_excludes = self.directory / 'excludes'
            frozen_excludes.write_bytes(global_excludes_content or b'')
            self._git(self.repository, 'config', 'core.excludesFile', str(frozen_excludes))
        self._git(self.repository, 'config', 'core.autocrlf', 'false')
        self._git(self.repository, 'add', '--force', '--all', '--', '.')
        empty_hooks = self.directory / 'hooks'
        empty_hooks.mkdir()
        self._git(self.repository, '-c', 'user.name=SlimeOps', '-c', 'user.email=workspace@localhost',
                  '-c', 'commit.gpgsign=false', '-c', f'core.hooksPath={empty_hooks}',
                  'commit', '--allow-empty', '-qm', 'Isolated workspace baseline')
        self._check_original()
        copied = {name: entry for name, entry in self._capture(self.repository).files.items() if entry is not None}
        if copied != {name: entry for name, entry in context_baseline.files.items() if entry is not None}:
            raise WorkspaceTransactionError('No se pudo conservar exactamente el contenido inicial del proyecto aislado.')
        self._prepared = True
        return str(self.sandbox)

    def publish(self) -> list[str]:
        if not self._prepared:
            raise WorkspaceTransactionError('Prepara el proyecto aislado antes de publicar sus cambios.')
        if self._published:
            return list(self._changes)
        isolated = {name: entry for name, entry in self._capture(self.sandbox).files.items() if entry is not None}
        before = {name: entry for name, entry in self._baseline.files.items() if entry is not None}
        changes = sorted(name for name in before.keys() | isolated.keys() if before.get(name) != isolated.get(name))
        self._check_original()
        staged: dict[str, Path] = {}
        backups: dict[str, Path] = {}
        applied: list[str] = []
        created_directories: list[Path] = []
        try:
            for name in changes:
                original = self._path(self.workspace, name)
                if self._file(self.workspace, name) != before.get(name):
                    raise WorkspaceConflictError('Un archivo de destino ya existe o cambió; conserva la copia de recuperación.')
                if name in before:
                    backup = self._path(self.directory / 'original', name)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, backup)
                    backups[name] = backup
                if name in isolated:
                    descriptor, filename = tempfile.mkstemp(prefix=f'.slimeops-{self.identifier}-', suffix='.tmp', dir=self.workspace)
                    os.close(descriptor)
                    temporary = Path(filename)
                    self._temporary_paths.add(temporary)
                    staged[name] = temporary
                    shutil.copy2(self._path(self.sandbox, name), temporary)
                    if self._file(self.workspace, temporary.name) != isolated[name]:
                        raise WorkspaceTransactionError('La copia aislada cambió mientras se preparaba su publicación.')
            # Validate the entire original again after staging, before replacing any file.
            self._check_original()
            for name in changes:
                target = self._path(self.workspace, name)
                if self._file(self.workspace, name) != before.get(name):
                    raise WorkspaceConflictError('Un archivo del proyecto cambió durante la publicación.')
                if name in isolated:
                    missing = []
                    parent = target.parent
                    while not parent.exists():
                        missing.append(parent)
                        parent = parent.parent
                    for directory in reversed(missing):
                        directory.mkdir()
                        created_directories.append(directory)
                    self._path(self.workspace, name)
                    os.replace(staged[name], target)
                else:
                    target.unlink()
                applied.append(name)
            prefix = self.workspace.relative_to(self._source_root)
            rooted_changes = {(prefix / name).as_posix(): isolated.get(name) for name in changes}
            expected_files = dict(self._context_baseline.files)
            expected_files.update(rooted_changes)
            expected = WorkspaceState(self._context_baseline.head, self._context_baseline.index, expected_files)
            if (self._capture(self._source_root, list(rooted_changes)) != expected
                    or self._read_exclude() != self._exclude_content
                    or self._read_global_excludes()[0] != self._global_excludes_signature):
                raise WorkspaceConflictError('El proyecto cambió durante la publicación; conserva la copia de recuperación.')
            self._published = True
            self._changes = changes
            return list(changes)
        except Exception as error:
            for name in reversed(applied):
                target = self._path(self.workspace, name)
                # Never overwrite another edit made after our replacement.
                if self._file(self.workspace, name) != isolated.get(name):
                    continue
                if name in backups:
                    # Recovery storage can be on a different volume than the project.
                    descriptor, filename = tempfile.mkstemp(prefix=f'.slimeops-{self.identifier}-', suffix='.tmp', dir=self.workspace)
                    os.close(descriptor)
                    temporary = Path(filename)
                    self._temporary_paths.add(temporary)
                    try:
                        shutil.copy2(backups[name], temporary)
                        os.replace(temporary, target)
                    finally:
                        if temporary.exists():
                            temporary.unlink()
                elif target.exists():
                    target.unlink()
            for directory in reversed(created_directories):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            if isinstance(error, WorkspaceTransactionError):
                raise
            raise WorkspaceTransactionError('No se pudieron publicar los archivos. Conserva la copia de recuperación.') from error
        finally:
            for temporary in staged.values():
                if temporary.exists():
                    temporary.unlink()
            self._temporary_paths.clear()

    def cleanup(self) -> None:
        """Failed/conflicted transactions stay available for explicit recovery."""
        if not self._published or not self.directory.exists():
            return
        target = self.directory.resolve()
        if (target != self.storage_root / self.identifier or not target.is_relative_to(self.storage_root)
                or self.directory.is_symlink() or (hasattr(self.directory, 'is_junction') and self.directory.is_junction())):
            raise WorkspaceTransactionError('La ruta de recuperación cambió; no se ha eliminado.')
        def remove_readonly(function, filename, error):
            path = Path(filename)
            if (not isinstance(error, PermissionError) or path.is_symlink()
                    or not path.resolve().is_relative_to(target) or function not in {os.unlink, os.rmdir}):
                raise error
            path.chmod(path.stat().st_mode | stat.S_IWUSR)
            function(filename)

        if sys.version_info >= (3, 12):
            shutil.rmtree(target, onexc=remove_readonly)
        else:
            shutil.rmtree(target, onerror=lambda function, filename, info: remove_readonly(function, filename, info[1]))
