"""Project paths and defaults; no runtime side effects."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_CATALOG = {
    "codex": ["gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna"],
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
}

CORS_ORIGINS = ['http://127.0.0.1:5500', 'http://localhost:5500', 'http://127.0.0.1:4173', 'http://localhost:4173', 'http://127.0.0.1:8000', 'https://agent-roster-pixel-20261022.blondmesa11.chatgpt.site']
