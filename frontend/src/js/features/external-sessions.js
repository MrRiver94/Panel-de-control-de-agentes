import { $ } from '../dom.js';
import { State } from '../state.js';
import { fetchApi } from '../services/api.js';
import { syncDashboard } from '../services/live.js';

let previous = '';
export function renderExternalSessions() {
  const list = $('#externalSessionsList');
  if (!list) return;
  const encoded = JSON.stringify([
    State.externalSessions,
    State.agents.map((agent) => [agent.id, agent.name]),
  ]);
  if (encoded === previous) return;
  previous = encoded;
  const rows = State.externalSessions.map((session) => {
    const row = document.createElement('div');
    row.className = 'ExternalSessionRow';
    const title = document.createElement('span');
    title.textContent = `${session.agent_name || session.source} · ${session.id.slice(0, 8)} · ${session.status}${session.signal_stale ? ' (último estado no confirmado)' : ''}`;
    const select = document.createElement('select');
    select.setAttribute('aria-label', `Slime para la sesión ${session.id}`);
    select.append(new Option(`Automático · ${session.agent_id.toUpperCase()}`, ''));
    State.agents.forEach((agent) => select.append(new Option(agent.name, agent.id)));
    select.value = session.binding === 'manual' ? session.agent_id : '';
    select.addEventListener('change', async () => {
      select.disabled = true;
      try {
        await fetchApi('/api/session-bindings', {
          method: 'POST',
          body: JSON.stringify({ session_id: session.id, agent_id: select.value || null }),
        });
        await syncDashboard();
      } catch (error) {
        title.textContent = error.message;
      } finally {
        select.disabled = false;
      }
    });
    row.append(title, select);
    return row;
  });
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.textContent = 'No hay sesiones externas registradas para este proyecto.';
    rows.push(empty);
  }
  list.replaceChildren(...rows);
}
