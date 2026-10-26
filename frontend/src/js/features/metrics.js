import { operationalHealth } from './health.js';
import { $, formatNumber } from '../dom.js';
import { State } from '../state.js';

function renderMetricsPanel() {
  const {
    tokens: used,
    active,
    occupancy: usage,
    availability: margin,
    status: health,
  } = operationalHealth(State.agents);
  $('#budgetUsage').textContent = `${usage}%`;
  $('#budgetMargin').textContent = `${margin}%`;
  $('#activeAgents').textContent = `${active}/${State.agents.length}`;
  $('#budgetHealth').textContent = health;
  $('#budgetBar').style.width = `${Math.min(100, usage)}%`;
  $('#budgetNumbers').textContent = `${formatNumber(used)} tokens medidos`;
  $('#efficiencyMessage').textContent = 'Ocupación de agentes · tokens de su última fase';
  $('#telemetryStamp').textContent = State.lastTelemetryAt
    ? `Actualizado ${State.lastTelemetryAt.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' })} · ${State.connected ? 'API en directo' : 'sin conexión'}`
    : 'Esperando telemetría';
}

function formatReset(unixSeconds) {
  if (!unixSeconds) return 'Sin dato de reinicio';
  const date = new Date(unixSeconds * 1000);
  return `Reinicia ${date.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })} · ${date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}`;
}

function renderCodexUsage() {
  const usage = State.codexUsage;
  if (!usage) return;
  if (!usage.available) {
    $('#codexUsageStatus').textContent = 'Uso local no disponible: abre Codex en este equipo.';
    return;
  }
  const latestDay = usage.daily_buckets?.at(-1);
  $('#fiveHourRemaining').textContent = `${usage.five_hour.remaining_percent}%`;
  $('#weeklyRemaining').textContent = `${usage.weekly.remaining_percent}%`;
  $('#fiveHourReset').textContent = formatReset(usage.five_hour.resets_at);
  $('#weeklyReset').textContent = formatReset(usage.weekly.resets_at);
  $('#codexPlan').textContent = `Plan ${(usage.plan || '—').toUpperCase()}`;
  $('#resetCredits').textContent = `${usage.reset_credits} recargas`;
  $('#dailyTokens').textContent = latestDay
    ? `${formatNumber(latestDay.tokens)} tokens · último día`
    : 'Actividad sin datos';
  $('#codexUsageStatus').textContent =
    `Datos reales de Codex · ${new Date(usage.refreshed_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
}

export { renderMetricsPanel, formatReset, renderCodexUsage };
