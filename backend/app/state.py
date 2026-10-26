"""Shared local roster, database location and telemetry caches."""
from datetime import datetime, timezone
from typing import Any
import threading

from .config import DATA_DIRECTORY
from .models import AgentState

agents: dict[str, AgentState] = {
    "director": AgentState(
        id='director',
        name='DIRECTOR',
        role='Dirección global',
        status='standby',
        tone='#ffd166',
        token_budget=6000,
        tokens_used=0,
        reasoning_effort='high',
        display_hue='-100deg',
        idle_mode='Coffee',
        default_action='priorizando',
        enabled_actions=['coordinar', 'priorizar'],
    ),
    "nexus": AgentState(
        id='nexus',
        name='NEXUS',
        role='Coordinador operativo',
        status='standby',
        tone='#d8ff5c',
        token_budget=8000,
        tokens_used=0,
        reasoning_effort='high',
        display_hue='68deg',
        idle_mode='Eating',
        default_action='planificando',
        enabled_actions=['coordinar', 'planificar'],
    ),
    "scout": AgentState(
        id='scout',
        name='SCOUT',
        role='Investigación',
        status='standby',
        tone='#57e5ff',
        token_budget=5500,
        tokens_used=0,
        display_hue='0deg',
        idle_mode='Sleep',
        default_action='investigando',
        enabled_actions=['investigar', 'analizar'],
    ),
    "forge": AgentState(
        id='forge',
        name='FORGE',
        role='Constructor',
        tone='#ff6b9a',
        token_budget=7000,
        tokens_used=0,
        display_hue='135deg',
        idle_mode='Sleep',
        default_action='construyendo',
        enabled_actions=['construir', 'implementar'],
    ),
    "sentinel": AgentState(
        id='sentinel',
        name='SENTINEL',
        role='Control de calidad',
        tone='#9383ff',
        token_budget=4500,
        tokens_used=0,
        reasoning_effort='low',
        display_hue='230deg',
        idle_mode='Coffee',
        default_action='revisando',
        enabled_actions=['revisar', 'auditar'],
    ),
    "muse": AgentState(
        id='muse',
        name='MUSE',
        role='Dirección de arte',
        tone='#ffaf5f',
        token_budget=6200,
        tokens_used=0,
        reasoning_effort='high',
        display_hue='-45deg',
        idle_mode='Eating',
        default_action='diseñando',
        enabled_actions=['diseñar', 'ilustrar'],
    ),
}
BUILTIN_AGENT_IDS = frozenset(agents)
AUDIT_DATABASE = DATA_DIRECTORY / "agent_activity.sqlite3"
# Lock order is runtime manager -> roster -> audit. Readers copy the roster while
# holding roster_lock; writers publish their replacement only after DB commit.
roster_lock = threading.RLock()
audit_lock = threading.RLock()
last_telemetry_sample = datetime.now(timezone.utc)
codex_usage_cache: dict[str, Any] | None = None
codex_usage_cached_at: datetime | None = None
codex_usage_lock = threading.Lock()
