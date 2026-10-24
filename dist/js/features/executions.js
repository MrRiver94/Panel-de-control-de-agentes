import { $ } from '../dom.js';
import { fetchApi } from '../services/api.js';
import { State } from '../state.js';

const ActiveStatuses = new Set(['queued', 'running', 'cancelling']);
const Labels = {
  queued: 'EN COLA',
  running: 'EN EJECUCIÓN',
  cancelling: 'CANCELANDO',
  completed: 'COMPLETADA',
  failed: 'ERROR',
  cancelled: 'CANCELADA',
  interrupted: 'INTERRUMPIDA',
  skipped: 'OMITIDA',
  no_changes: 'SIN CAMBIOS',
};
let lastHistory = '';
let refreshing = false;

function textElement(tag, text) {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
}

function renderExecutions(executions) {
  State.executionBusy = executions.some((item) => ActiveStatuses.has(item.status));
  $('#submitMission').disabled = State.executionBusy || !State.runtimeReady;
  const encoded = JSON.stringify(executions);
  if (encoded === lastHistory) return;
  lastHistory = encoded;
  const openIds = new Set(
    [...document.querySelectorAll('.ExecutionRecord[open]')].map((item) => item.dataset.id),
  );
  $('#executionHistory').replaceChildren(
    ...executions.map((execution) => {
      const record = document.createElement('details');
      record.className = 'ExecutionRecord';
      record.dataset.id = execution.id;
      record.dataset.status = execution.status;
      record.open = openIds.has(execution.id) || ActiveStatuses.has(execution.status);
      record.append(
        textElement(
          'summary',
          `${execution.status === 'completed' ? (execution.sandbox === 'read-only' ? 'PROPUESTA LISTA' : execution.changed_files?.length ? 'CAMBIOS GENERADOS' : 'TURNOS FINALIZADOS · CAMBIOS NO VERIFICADOS') : Labels[execution.status] || execution.status} · ${execution.prompt}`,
        ),
      );
      record.append(
        textElement(
          'p',
          `${execution.workspace} · ${execution.sandbox === 'workspace-write' ? 'Cambios permitidos' : 'Solo lectura'} · ${new Date(execution.created_at).toLocaleString('es-ES')}`,
        ),
      );
      if (ActiveStatuses.has(execution.status)) {
        const button = textElement('button', 'CANCELAR MISIÓN');
        button.type = 'button';
        button.disabled = execution.status === 'cancelling';
        button.addEventListener('click', async () => {
          button.disabled = true;
          try {
            await fetchApi(`/api/executions/${execution.id}/cancel`, { method: 'POST' });
            await syncExecutions();
          } catch (error) {
            $('#missionSummary').textContent = error.message;
            button.disabled = false;
          }
        });
        record.append(button);
      }
      if (execution.error) record.append(textElement('p', execution.error));
      if (execution.outcome) record.append(textElement('p', execution.outcome));
      if (execution.changed_files?.length) {
        record.append(textElement('p', 'ARCHIVOS CAMBIADOS DURANTE LA MISIÓN'));
        record.append(textElement('pre', execution.changed_files.join('\n')));
      }
      execution.steps.forEach((step) => {
        const section = document.createElement('section');
        section.className = 'ExecutionStep';
        section.append(
          textElement(
            'b',
            `${step.name} · ${step.status === 'completed' ? 'FASE FINALIZADA' : Labels[step.status] || step.status}`,
          ),
        );
        const usage = step.usage;
        section.append(
          textElement(
            'p',
            `${step.model || 'Modelo de Codex local'} · ${step.effort} · ${usage ? `${(usage.input_tokens + usage.output_tokens).toLocaleString('es-ES')} tokens medidos` : 'Consumo aún no disponible'}${step.session_id ? ` · sesión ${step.session_id}` : ''}`,
          ),
        );
        if (step.result) section.append(textElement('pre', step.result));
        record.append(section);
      });
      return record;
    }),
  );
}

async function syncExecutions() {
  if (refreshing) return;
  refreshing = true;
  try {
    renderExecutions(await fetchApi('/api/executions'));
  } catch {
    State.runtimeReady = false;
    $('#submitMission').disabled = true;
    $('#runtimeStatus').textContent =
      'Sin conexión con el runtime local. Pulsa RECONECTAR cuando la API esté disponible.';
  } finally {
    refreshing = false;
  }
}

async function syncRuntime() {
  try {
    const runtime = await fetchApi('/api/runtime');
    State.runtimeReady = runtime.ready;
    if (!$('#runtimeWorkspace').value) $('#runtimeWorkspace').value = runtime.workspace;
    $('#runtimeStatus').textContent = runtime.message;
    $('#submitMission').disabled = !runtime.ready || State.executionBusy;
    await syncExecutions();
  } catch (error) {
    State.runtimeReady = false;
    $('#submitMission').disabled = true;
    $('#runtimeStatus').textContent = `Codex no disponible: ${error.message}`;
  }
}

function startExecutions() {
  $('#submitMission').disabled = true;
  $('#refreshRuntime').addEventListener('click', syncRuntime);
  syncRuntime();
  setInterval(syncExecutions, 2000);
}

export { startExecutions, syncExecutions, syncRuntime };
