"""Local provider diagnostics. Never read or return authentication files."""
from __future__ import annotations

from pathlib import Path
import threading
import time

from .codex_process import find_codex, login_ready
from .codex_sessions import _sessions_root, get_codex_sessions
from .config import FROZEN, PROJECT_ROOT, monitor_only
from .timeutils import now

SUPPORTED_SOURCES = frozenset({'vscode', 'cli', 'subagent'})
_account_lock = threading.Lock()
_account_cache: tuple[str | None, float, dict] | None = None


def default_workspace() -> str:
    """An empty project selection follows the latest observed external project."""
    for session in get_codex_sessions(external_only=True)['sessions']:
        workspace = session.get('workspace')
        if session.get('source') in SUPPORTED_SOURCES and workspace and Path(workspace).is_dir():
            return workspace
    return str(Path.home() if FROZEN else PROJECT_ROOT)


def account_status() -> dict:
    global _account_cache
    executable = find_codex()
    with _account_lock:
        if _account_cache and _account_cache[0] == executable and time.monotonic() - _account_cache[1] < 60:
            return dict(_account_cache[2])
        if executable:
            connected, message = login_ready(executable)
            account = {'status': 'connected' if connected else 'unavailable', 'message': message}
        else:
            account = {'status': 'cli_missing', 'message': 'No se encontró el ejecutable de Codex. Puedes seguir leyendo sus sesiones locales si existen.'}
        _account_cache = (executable, time.monotonic(), account)
        return dict(account)


def local_status() -> dict:
    sessions = get_codex_sessions(external_only=True)
    visible = [item for item in sessions['sessions'] if item.get('source') in SUPPORTED_SOURCES]
    projects = {}
    for session in visible:
        workspace = session.get('workspace')
        if not workspace or workspace in projects:
            continue
        projects[workspace] = {'workspace': workspace, 'name': session['project'], 'updated_at': session['updated_at']}
    status = sessions.get('status', 'ready' if visible else 'empty')
    messages = {
        'missing': 'Todavía no hay una carpeta de sesiones de Codex. Abre Codex en VS Code o en la terminal y realiza una tarea.',
        'empty': 'No se encontraron sesiones compatibles. Abre Codex en VS Code o en la terminal y realiza una tarea.',
        'unreadable': 'No se pueden leer las sesiones de Codex. Revisa los permisos de su carpeta local.',
        'ready': 'Monitor leyendo actividad local de Codex. No inicia tareas ni consume inferencias.',
    }
    if not visible and status == 'ready':
        status = 'empty'
    return {
        'provider': 'codex', 'monitor_only': monitor_only(), 'status': status,
        'message': messages[status], 'sessions_directory': str(_sessions_root()),
        'account': account_status(), 'projects': list(projects.values()),
        'sources': {source: sum(item.get('source') == source for item in visible) for source in sorted(SUPPORTED_SOURCES)},
        'session_count': len(visible), 'refreshed_at': now().isoformat(),
        'providers': [{'id': 'codex', 'available': True}, {'id': 'anthropic', 'available': False}],
    }
