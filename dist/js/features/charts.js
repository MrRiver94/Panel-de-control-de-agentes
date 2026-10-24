import { $, formatNumber } from '../dom.js';
import { State } from '../state.js';

const compactTokens = (value) =>
  new Intl.NumberFormat('es-ES', { notation: 'compact', maximumFractionDigits: 1 }).format(value);

const chartGrid = '<path class="ChartGrid" d="M10 24H350 M10 67H350 M10 110H350" />';

function emptyUsageChart(id, message) {
  const box = $(id);
  box.innerHTML = `<div class="UsageChartEmpty">${message}</div>`;
  box.setAttribute('aria-label', message);
}

function renderAgentUsageChart() {
  const points = (State.agentUsageSeries?.points || [])
    .map((point) => ({ time: Date.parse(point.at), rate: Number(point.tokens_per_minute) }))
    .filter((point) => Number.isFinite(point.time) && Number.isFinite(point.rate));
  if (points.length < 2) {
    emptyUsageChart('#agentUsageChart', 'Esperando dos muestras del medidor');
    $('#agentPeak').textContent = 'PICO —';
    $('#agentUsageNote').textContent =
      'El historial comienza ahora; no se inventan datos anteriores.';
    return;
  }
  const end = Date.now();
  const start = end - 60 * 60 * 1000;
  const peakRate = Math.max(...points.map((point) => point.rate));
  const maximum = Math.max(1, peakRate);
  const coords = points.map((point) => [
    Math.max(10, Math.min(350, 10 + ((point.time - start) / (end - start)) * 340)),
    110 - (point.rate / maximum) * 82,
  ]);
  const path = coords
    .map(([x, y], index) => `${index ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(' ');
  const [peakX, peakY] = coords[points.findIndex((point) => point.rate === peakRate)];
  const [lastX, lastY] = coords.at(-1);
  $('#agentUsageChart').innerHTML =
    `<svg viewBox="0 0 360 132" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="agentChartFill" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#7ee2e8" stop-opacity=".28"/><stop offset="1" stop-color="#7ee2e8" stop-opacity="0"/></linearGradient></defs>${chartGrid}<path d="${path} L${lastX.toFixed(1)} 110 L${coords[0][0].toFixed(1)} 110 Z" fill="url(#agentChartFill)"/><path class="ChartLine" d="${path}"/><circle class="ChartPoint ChartPeak" cx="${peakX.toFixed(1)}" cy="${peakY.toFixed(1)}" r="5"/><circle class="ChartPoint" cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="4"/></svg>`;
  $('#agentUsageChart').setAttribute(
    'aria-label',
    `Ritmo de uso de agentes durante la última hora. Pico ${formatNumber(peakRate)} tokens por minuto.`,
  );
  $('#agentPeak').textContent = `PICO ${compactTokens(peakRate)}`;
  $('#agentUsageNote').textContent =
    `${points.length} muestras guardadas · ritmo del medidor local`;
}

function renderCodexUsageChart() {
  const buckets = State.codexUsage?.available ? State.codexUsage.daily_buckets || [] : [];
  const byDay = new Map(
    buckets
      .filter(
        (row) => /^\d{4}-\d{2}-\d{2}$/.test(row.startDate) && Number.isFinite(Number(row.tokens)),
      )
      .map((row) => [row.startDate, Math.max(0, Number(row.tokens))]),
  );
  if (!byDay.size) {
    emptyUsageChart('#codexUsageChart', 'Sin historial diario de Codex disponible');
    $('#codexPeak').textContent = 'PICO —';
    $('#codexUsageNote').textContent = 'Conecta la API local para consultar el uso diario.';
    return;
  }
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, index) =>
    new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate() - 6 + index))
      .toISOString()
      .slice(0, 10),
  );
  const values = days.map((day) => byDay.get(day) || 0);
  const maximum = Math.max(...values);
  if (!maximum) {
    emptyUsageChart('#codexUsageChart', 'Aún no hay tokens en los últimos 7 días');
    $('#codexPeak').textContent = 'PICO —';
    return;
  }
  const peakIndex = values.indexOf(maximum);
  const bars = values
    .map((value, index) => {
      const height = value ? Math.max(3, (value / maximum) * 82) : 0;
      const x = 19 + index * 46;
      return `<rect class="${index === peakIndex ? 'ChartBarPeak' : 'ChartBar'}" x="${x}" y="${(110 - height).toFixed(1)}" width="28" height="${height.toFixed(1)}" rx="1"><title>${days[index]} · ${formatNumber(value)} tokens</title></rect><text x="${x + 14}" y="125" text-anchor="middle">${Number(days[index].slice(-2))}</text>`;
    })
    .join('');
  $('#codexUsageChart').innerHTML =
    `<svg viewBox="0 0 360 132" preserveAspectRatio="none" aria-hidden="true">${chartGrid}${bars}</svg>`;
  $('#codexUsageChart').setAttribute(
    'aria-label',
    `Tokens diarios de Codex en los últimos siete días. Pico ${formatNumber(maximum)} tokens el ${days[peakIndex]}.`,
  );
  $('#codexPeak').textContent = `PICO ${compactTokens(maximum)}`;
  $('#codexUsageNote').textContent = `Máximo ${days[peakIndex]} · ${formatNumber(maximum)} tokens`;
}

export { compactTokens, chartGrid, emptyUsageChart, renderAgentUsageChart, renderCodexUsageChart };
