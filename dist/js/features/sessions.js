import { fetchApi } from '../services/api.js';
import { State } from '../state.js';

const SourceLabels = { vscode: 'VS Code', cli: 'Terminal', subagent: 'Subagente' };
let pending = false;
let diagnosticPending = false;

export async function refreshLocalMonitor() {
  if (diagnosticPending) return;
  diagnosticPending = true;
  const status = document.getElementById('localMonitorStatus');
  const account = document.getElementById('localAccountStatus');
  try {
    const data = await fetchApi('/api/local-status');
    status.textContent = data.message;
    account.textContent = data.account.message;
    document.getElementById('localMonitorDirectory').textContent =
      `Sesiones: ${data.sessions_directory}`;
    const select = document.getElementById('monitorProjectSelect');
    const options = [new Option('Automático · último proyecto activo', '')];
    for (const project of data.projects)
      options.push(new Option(`${project.name} · ${project.workspace}`, project.workspace));
    if (
      State.monitorWorkspace &&
      !data.projects.some((item) => item.workspace === State.monitorWorkspace)
    )
      options.push(new Option(State.monitorWorkspace, State.monitorWorkspace));
    select.replaceChildren(...options);
    select.value = State.monitorWorkspace;
  } catch {
    status.textContent = 'Monitor desconectado. Abre SlimeOps para volver a leer la actividad.';
    account.textContent = 'No se pudo comprobar la conexión con Codex.';
  } finally {
    diagnosticPending = false;
  }
}

export function startCodexSessions() {
  const statusNode = document.getElementById('codexSessionsStatus');
  const listNode = document.getElementById('codexSessionsList');

  function addCell(parent, tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = value;
    parent.append(node);
    return node;
  }

  async function refreshCodexSessions() {
    if (pending) return;
    pending = true;
    try {
      const data = await fetchApi('/api/codex-sessions');
      listNode.replaceChildren();
      statusNode.textContent = data.available
        ? `${data.sessions.length} sesiones recientes · datos locales de Codex`
        : 'No se encontraron rollouts locales de Codex.';
      for (const session of data.sessions.slice(0, 8)) {
        const row = document.createElement('div');
        row.className = 'CodexSessionRow';
        addCell(row, 'b', '', session.project);
        addCell(
          row,
          'small',
          '',
          `${SourceLabels[session.source] || 'Codex'} · ${session.status} · ${session.usage?.total_tokens?.toLocaleString('es-ES') ?? '—'} tokens`,
        );
        listNode.append(row);
      }
    } catch {
      statusNode.textContent = 'API local desconectada; no se pudieron leer las sesiones.';
    } finally {
      pending = false;
    }
  }

  refreshCodexSessions();
  refreshLocalMonitor();
  document.getElementById('refreshLocalMonitor').addEventListener('click', () => {
    refreshLocalMonitor();
    refreshCodexSessions();
  });
  setInterval(refreshCodexSessions, 15000);
  setInterval(refreshLocalMonitor, 60000);
}
