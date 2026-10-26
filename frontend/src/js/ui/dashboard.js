import { $ } from '../dom.js';
import { renderActivityLog, renderTerminal } from '../features/activity.js';
import { renderAgentWatchPanels } from '../features/agent-watch.js';
import { renderControlPanel } from '../features/controls.js';
import { renderCodexUsage, renderMetricsPanel } from '../features/metrics.js';
import { renderSlimeRoom } from '../room/render.js';
import { State } from '../state.js';
import { renderExternalSessions } from '../features/external-sessions.js';

function renderDashboard() {
  renderControlPanel();
  renderMetricsPanel();
  renderCodexUsage();
  renderActivityLog();
  renderTerminal();
  renderSlimeRoom();
  renderAgentWatchPanels();
  renderExternalSessions();
}

function updateConnectionLabel() {
  $('#apiStatus').textContent = State.connected
    ? '● API CONECTADA'
    : '● SIN CONEXIÓN · ÚLTIMO ESTADO';
  $('#apiStatus').style.color = State.connected ? 'var(--acid)' : 'var(--cyan)';
}

function updateDigitalClock() {
  const now = new Date();
  $('#digitalTime').textContent = now.toLocaleTimeString('es-ES', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const date = new Intl.DateTimeFormat('es-ES', {
    weekday: 'long',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
    .format(now)
    .replace('.', '')
    .toUpperCase();
  $('#digitalDate').textContent = date.replace(',', ' ·');
}

export { renderDashboard, updateConnectionLabel, updateDigitalClock };
