import { visualStatus } from '../agents/model.js';
import { $, formatNumber } from '../dom.js';
import { State } from '../state.js';

function renderMetricsPanel() {
  const used = State.agents.reduce((sum, agent) => sum + agent.tokens_used, 0);
  const budget = State.agents.reduce((sum, agent) => sum + agent.token_budget, 0);
  const active = State.agents.filter(
    (agent) => agent.status === 'working' && visualStatus(agent) !== 'error',
  ).length;
  const usage = Math.round((used / budget) * 100);
  const margin = Math.max(0, 100 - usage);
  const health = usage < 65 ? 'EFICIENTE' : usage < 85 ? 'VIGILAR' : 'REVISAR';
  $('#budgetUsage').textContent = `${usage}%`;
  $('#budgetMargin').textContent = `${margin}%`;
  $('#activeAgents').textContent = `${active}/${State.agents.length}`;
  $('#budgetHealth').textContent = health;
  $('#budgetBar').style.width = `${Math.min(100, usage)}%`;
  $('#budgetNumbers').textContent = `${formatNumber(used)} / ${formatNumber(budget)} tokens`;
  $('#efficiencyMessage').textContent = 'Consumo medido · presupuesto orientativo';
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
