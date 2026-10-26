import { $ } from '../dom.js';
import { fetchApi } from '../services/api.js';
import { State } from '../state.js';
import { syncDashboard, connectLiveStream } from '../services/live.js';

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
  needs_review: 'CAMBIOS CON OBSERVACIONES',
};
let lastHistory = '';
let refreshing = false;
let runtimeRefreshing = false;

function textElement(tag, text) {
  const element = document.createElement(tag);
  element.textContent = text;
  return element;
}

function appendResults(section, step) {
  if (step.review) {
    section.append(
      textElement(
        'p',
        `REVISIÓN · ${step.review.verdict === 'approved' ? 'SIN OBSERVACIONES BLOQUEANTES' : 'REQUIERE REVISIÓN'}`,
      ),
    );
    section.append(textElement('p', step.review.summary));
    step.review.findings.forEach((finding) =>
      section.append(
        textElement(
          'p',
          `${finding.severity.toUpperCase()} · ${finding.path || 'General'}${finding.line ? ':' + finding.line : ''} · ${finding.message}`,
        ),
      ),
    );
  } else if (step.result) section.append(textElement('pre', step.result));
}

function renderExecutions(executions) {
  State.executionBusy = executions.some((item) => ActiveStatuses.has(item.status));
  $('#submitMission').disabled = State.executionBusy || !State.runtimeReady;
  const encoded = JSON.stringify([executions, State.runtimeReady, State.executionBusy]);
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
      if (
        ['failed', 'cancelled', 'interrupted', 'no_changes', 'needs_review'].includes(
          execution.status,
        )
      ) {
        const retry = textElement('button', 'REINTENTAR MISIÓN');
        retry.type = 'button';
        retry.disabled = State.executionBusy || !State.runtimeReady;
        retry.addEventListener('click', async () => {
          retry.disabled = true;
          try {
            await fetchApi(`/api/executions/${execution.id}/retry`, { method: 'POST' });
            await syncExecutions();
          } catch (error) {
            $('#missionSummary').textContent = error.message;
            retry.disabled = false;
          }
        });
        record.append(retry);
      }
      if (execution.outcome) record.append(textElement('p', execution.outcome));
      if (execution.changed_files?.length) {
        record.append(textElement('p', 'ARCHIVOS CAMBIADOS DURANTE LA MISIÓN'));
        record.append(textElement('pre', execution.changed_files.join('\n')));
        const diffButton = textElement('button', 'VER DIFF DE ESTA MISIÓN');
        diffButton.type = 'button';
        const diffView = document.createElement('div');
        diffButton.addEventListener('click', async () => {
          diffButton.disabled = true;
          try {
            const result = await fetchApi(`/api/executions/${execution.id}/diff`);
            diffView.replaceChildren();
            if (!result.files.length)
              diffView.append(
                textElement(
                  'p',
                  'Esta misión no tiene un diff guardado; los registros anteriores conservan solo la lista de archivos.',
                ),
              );
            result.files.forEach((file) => {
              const item = document.createElement('details');
              item.append(
                textElement(
                  'summary',
                  `${file.path}${file.binary ? ' · binario' : ''}${file.redacted ? ' · contenido protegido' : ''}${file.truncated ? ' · vista parcial' : ''}`,
                ),
              );
              item.append(textElement('pre', file.patch));
              diffView.append(item);
            });
          } catch (error) {
            diffView.replaceChildren(textElement('p', error.message));
            diffButton.disabled = false;
          }
        });
        record.append(diffButton, diffView);
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
        appendResults(section, step);
        record.append(section);
      });
      if (execution.steps.some((step) => step.has_result || step.has_review)) {
        const load = textElement('button', 'CARGAR RESULTADOS Y REVISIÓN');
        load.type = 'button';
        const results = document.createElement('div');
        load.addEventListener('click', async () => {
          load.disabled = true;
          try {
            const detail = await fetchApi(`/api/executions/${execution.id}`);
            results.replaceChildren();
            detail.steps.forEach((step) => {
              const section = document.createElement('section');
              section.className = 'ExecutionStep';
              section.append(textElement('b', step.name));
              appendResults(section, step);
              results.append(section);
            });
            if (ActiveStatuses.has(detail.status)) {
              load.textContent = 'ACTUALIZAR RESULTADOS';
              load.disabled = false;
            }
          } catch (error) {
            results.replaceChildren(textElement('p', error.message));
            load.disabled = false;
          }
        });
        record.append(load, results);
      }
      return record;
    }),
  );
}

async function syncExecutions() {
  if (refreshing) return;
  refreshing = true;
  try {
    renderExecutions(await fetchApi('/api/executions?summary=true'));
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
  if (runtimeRefreshing) return;
  runtimeRefreshing = true;
  try {
    const runtime = await fetchApi('/api/runtime');
    State.runtimeReady = runtime.ready;
    if (!$('#runtimeWorkspace').value)
      $('#runtimeWorkspace').value = State.monitorWorkspace || runtime.workspace;
    $('#runtimeStatus').textContent = runtime.message;
    $('#submitMission').disabled = !runtime.ready || State.executionBusy;
    await syncExecutions();
  } catch (error) {
    State.runtimeReady = false;
    $('#submitMission').disabled = true;
    $('#runtimeStatus').textContent = `Codex no disponible: ${error.message}`;
  } finally {
    runtimeRefreshing = false;
  }
}

function startExecutions() {
  $('#submitMission').disabled = true;
  $('#refreshRuntime').addEventListener('click', syncRuntime);
  $('#runtimeWorkspace').addEventListener('change', () => {
    State.monitorWorkspace = $('#runtimeWorkspace').value.trim();
    localStorage.setItem('slimeops-workspace', State.monitorWorkspace);
    if (State.eventSource) {
      State.eventSource.close();
      State.eventSource = null;
    }
    connectLiveStream();
    syncDashboard().catch(() => {});
  });
  syncRuntime();
  setInterval(syncExecutions, 2000);
  setInterval(() => {
    if (!State.runtimeReady) syncRuntime();
  }, 15000);
}

export { startExecutions, syncExecutions, syncRuntime };
