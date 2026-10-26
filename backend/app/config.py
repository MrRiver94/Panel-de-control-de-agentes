"""Project paths and defaults; no runtime side effects."""
from pathlib import Path
import os
import sys

FROZEN = bool(getattr(sys, 'frozen', False))
PROJECT_ROOT = Path(sys._MEIPASS) if FROZEN else Path(__file__).resolve().parents[2]


def local_data_directory() -> Path:
    """Keep user data outside the installed application and its release archive."""
    configured = os.environ.get('SLIMEOPS_DATA_DIR')
    if configured:
        return Path(configured).expanduser().resolve()
    if not FROZEN:
        return PROJECT_ROOT / 'data'
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'SlimeOps'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'SlimeOps'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'slimeops'


DATA_DIRECTORY = local_data_directory()


def monitor_only() -> bool:
    return os.environ.get('SLIMEOPS_MONITOR_ONLY', '1' if FROZEN else '0') == '1'
DEFAULT_MODEL_CATALOG = {
    "codex": ["gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna"],
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
}

CORS_ORIGINS = ['http://127.0.0.1:5500', 'http://localhost:5500', 'http://127.0.0.1:4173', 'http://localhost:4173', 'http://127.0.0.1:8000', 'https://agent-roster-pixel-20261022.blondmesa11.chatgpt.site']
