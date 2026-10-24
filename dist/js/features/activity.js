import { $, formatNumber, escapeHtml } from '../dom.js';
import { fetchApi } from '../services/api.js';
import { State } from '../state.js';

function eventLabel(event) {
  return event.kind.replaceAll('_', ' ').toUpperCase();
}

function renderActivityLog() {
  $('#activityLog').innerHTML =
    State.events
      .map(
        (event) =>
          `<article class="ActivityItem"><time>${new Date(event.created_at).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}</time><div><b>${escapeHtml(event.agent)} · ${escapeHtml(eventLabel(event))}</b><br><span>${escapeHtml(event.message)}</span></div></article>`,
      )
      .join('') || '<div class="ActivityItem"><time>—</time><span>Sin actividad aún.</span></div>';
}

function renderTerminal() {
  const events = State.events;
  const key = events.map((event) => event.id).join('|');
  if (key === State.terminalEventKey) return;
  State.terminalEventKey = key;
  const feed = $('#terminalFeed');
  const wasAtBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 24;
  const rows = events.length
    ? [...events].reverse().map((event) => {
        const line = document.createElement('div');
        line.className = `TerminalLine ${event.kind?.includes('error') ? 'IsError' : ''}`;
        const time = new Date(event.created_at).toLocaleTimeString('es-ES', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });
        line.textContent = `[${time}] ${event.agent} · ${event.kind}: ${event.message}`;
        return line;
      })
    : [
        Object.assign(document.createElement('div'), {
          className: 'TerminalLine',
          textContent: '[--:--:--] Esperando eventos de la API local…',
        }),
      ];
  feed.replaceChildren(...rows);
  $('#terminalCount').textContent = `${events.length} REGISTROS`;
  if (wasAtBottom) feed.scrollTop = feed.scrollHeight;
}

function renderAuditHistory() {
  const events = State.auditEvents.length ? State.auditEvents : State.events;
  $('#auditCount').textContent = `${events.length} EVENTOS GUARDADOS`;
  $('#auditHistory').innerHTML =
    events
      .map(
        (event) =>
          `<article class="AuditRecord"><time>${new Date(event.created_at).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'medium' })}</time><div><b>${escapeHtml(event.agent)}</b><em>${escapeHtml(eventLabel(event))}</em><p>${escapeHtml(event.message)}</p><small>ENTRADA ${formatNumber(event.input_tokens)} · SALIDA ${formatNumber(event.output_tokens)} · RAZONAMIENTO ${formatNumber(event.reasoning_tokens)} · TOTAL ${formatNumber(event.tokens)}</small></div></article>`,
      )
      .join('') || '<p class="AuditEmpty">Aún no hay actividad guardada.</p>';
}

async function openAuditHistory() {
  try {
    State.auditEvents = await fetchApi('/api/activity/history?limit=100');
  } catch {
    State.auditEvents = State.events;
  }
  renderAuditHistory();
  $('#auditDialog').showModal();
}

export { eventLabel, renderActivityLog, renderTerminal, renderAuditHistory, openAuditHistory };
