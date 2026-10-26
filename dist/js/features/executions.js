import { $, textElement } from '../dom.js';
import { fetchApi } from '../services/api.js';
import { State } from '../state.js';
import { syncDashboard, connectLiveStream, resetLiveContext } from '../services/live.js';

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
let refreshing = null;
let runtimeRefreshing = null;
const history = new Map();
const records = new Map();
const pageSize = 20;
let pageCursor = null;
let historyStarted = false;
let hasMore = true;
let loadingMore = false;
let historyGeneration = 0;
let historyOperator = State.operatorId;

function missionAllowed() {
  if (State.monitorOnly) return false;
  if (!State.access) return true;
  const user = State.access.users.find((item) => item.id === State.operatorId);
  const permissions =
    State.access.roles.find((role) => role.id === user?.role_id)?.permissions || [];
  return permissions.includes('*') || permissions.includes('mission.create');
}

function resetExecutionHistory() {
  historyGeneration += 1;
  historyOperator = State.operatorId;
  history.clear();
  records.clear();
  pageCursor = null;
  historyStarted = false;
  hasMore = true;
  loadingMore = false;
  State.runtimeReady = false;
  State.executionBusy = false;
  $('#submitMission').disabled = true;
  $('#executionHistory').replaceChildren();
  updateHistoryNavigation();
}

function updateHistoryNavigation() {
  let button = $('#loadOlderExecutions');
  if (!button) {
    button = textElement('button', 'CARGAR MISIONES ANTERIORES');
    button.id = 'loadOlderExecutions';
    button.type = 'button';
    $('#executionHistory').after(button);
    button.addEventListener('click', loadOlderExecutions);
  }
  button.hidden = !hasMore;
  button.disabled = loadingMore;
  button.textContent = loadingMore ? 'CARGANDO MISIONES…' : 'CARGAR MISIONES ANTERIORES';
}

function mergeExecutions(executions, older = false) {
  executions.forEach((execution) => {
    if (!older || !history.has(execution.id)) history.set(execution.id, execution);
  });
  renderExecutions(
    [...history.values()].sort(
      (a, b) => b.created_at.localeCompare(a.created_at) || b.id.localeCompare(a.id),
    ),
  );
}

async function loadOlderExecutions() {
  if (loadingMore || !hasMore) return;
  if (!historyStarted) await syncExecutions();
  if (!historyStarted || !hasMore || !pageCursor) return;
  const generation = historyGeneration;
  loadingMore = true;
  updateHistoryNavigation();
  try {
    const executions = await fetchApi(
      `/api/executions?summary=true&limit=${pageSize}&before=${encodeURIComponent(pageCursor)}`,
    );
    if (generation !== historyGeneration) return;
    if (executions.length) pageCursor = executions.at(-1).id;
    hasMore = executions.length === pageSize;
    mergeExecutions(executions, true);
  } catch (error) {
    if (generation === historyGeneration)
      $('#missionSummary').textContent = `No se pudo cargar el historial: ${error.message}`;
  } finally {
    if (generation === historyGeneration) {
      loadingMore = false;
      updateHistoryNavigation();
    }
  }
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
  $('#submitMission').disabled = State.executionBusy || !State.runtimeReady || !missionAllowed();
  const container = $('#executionHistory');
  const ids = new Set(executions.map((execution) => execution.id));
  for (const [id, entry] of records) {
    if (!ids.has(id)) {
      entry.record.remove();
      records.delete(id);
    }
  }
  executions.forEach((execution, index) => {
    let entry = records.get(execution.id);
    if (!entry) {
      const record = document.createElement('details');
      record.className = 'ExecutionRecord';
      record.dataset.id = execution.id;
      record.open = ActiveStatuses.has(execution.status);
      const summary = document.createElement('summary');
      const body = document.createElement('div');
      record.append(summary, body);
      entry = { record, summary, body, generation: historyGeneration };
      records.set(execution.id, entry);
    }
    const { record, summary, body } = entry;
    if (container.children[index] !== record)
      container.insertBefore(record, container.children[index] || null);
    const encoded = JSON.stringify(execution);
    // Keep the record, loaded panels and their selection/focus intact on unrelated updates.
    if (entry.encoded === encoded) {
      if (entry.retry)
        entry.retry.disabled = State.executionBusy || !State.runtimeReady || !missionAllowed();
      if (entry.cancel)
        entry.cancel.disabled = execution.status === 'cancelling' || !missionAllowed();
      return;
    }
    entry.encoded = encoded;
    record.dataset.status = execution.status;
    summary.textContent = `${execution.status === 'completed' ? (execution.sandbox === 'read-only' ? 'PROPUESTA LISTA' : execution.changed_files?.length ? 'CAMBIOS GENERADOS' : 'TURNOS FINALIZADOS · CAMBIOS NO VERIFICADOS') : Labels[execution.status] || execution.status} · ${execution.prompt}`;
    body.replaceChildren();
    entry.retry = null;
    entry.cancel = null;
    body.append(
      textElement(
        'p',
        `${execution.workspace} · ${execution.sandbox === 'workspace-write' ? 'Cambios permitidos' : 'Solo lectura'} · ${new Date(execution.created_at).toLocaleString('es-ES')}`,
      ),
    );
    if (ActiveStatuses.has(execution.status)) {
      const button = textElement('button', 'CANCELAR MISIÓN');
      button.type = 'button';
      entry.cancel = button;
      button.disabled = execution.status === 'cancelling' || !missionAllowed();
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
      body.append(button);
    }
    if (execution.error) body.append(textElement('p', execution.error));
    if (
      ['failed', 'cancelled', 'interrupted', 'no_changes', 'needs_review'].includes(
        execution.status,
      )
    ) {
      const retry = textElement('button', 'REINTENTAR MISIÓN');
      retry.type = 'button';
      entry.retry = retry;
      retry.disabled = State.executionBusy || !State.runtimeReady || !missionAllowed();
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
      body.append(retry);
    }
    if (execution.outcome) body.append(textElement('p', execution.outcome));
    if (execution.recovery_workspace) {
      body.append(
        textElement(
          'p',
          'Los resultados se conservaron en una copia aislada para revisar y recuperar los cambios:',
        ),
      );
      body.append(textElement('pre', execution.recovery_workspace));
    }
    if (execution.changed_files?.length) {
      body.append(textElement('p', 'ARCHIVOS CAMBIADOS DURANTE LA MISIÓN'));
      body.append(textElement('pre', execution.changed_files.join('\n')));
    }
    if (execution.changed_files?.length && !entry.diffPanel) {
      entry.diffPanel = document.createElement('div');
      entry.diffPanel.className = 'ExecutionDiff';
      const diffButton = textElement('button', 'VER DIFF DE ESTA MISIÓN');
      diffButton.type = 'button';
      const diffView = document.createElement('div');
      diffButton.addEventListener('click', async () => {
        diffButton.disabled = true;
        try {
          const result = await fetchApi(`/api/executions/${execution.id}/diff`);
          if (entry.generation !== historyGeneration) return;
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
      entry.diffPanel.append(diffButton, diffView);
      record.append(entry.diffPanel);
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
      body.append(section);
    });
    if (execution.steps.some((step) => step.has_result || step.has_review) && !entry.resultsPanel) {
      entry.resultsPanel = document.createElement('div');
      entry.resultsPanel.className = 'ExecutionResults';
      const load = textElement('button', 'CARGAR RESULTADOS Y REVISIÓN');
      load.type = 'button';
      const results = document.createElement('div');
      load.addEventListener('click', async () => {
        load.disabled = true;
        try {
          const detail = await fetchApi(`/api/executions/${execution.id}`);
          if (entry.generation !== historyGeneration) return;
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
      entry.resultsPanel.append(load, results);
      record.append(entry.resultsPanel);
    }
  });
}

async function syncExecutions() {
  if (historyOperator !== State.operatorId) resetExecutionHistory();
  if (refreshing === historyGeneration) return;
  const generation = historyGeneration;
  refreshing = generation;
  try {
    const executions = await fetchApi(`/api/executions?summary=true&limit=${pageSize}`);
    if (generation !== historyGeneration) return;
    if (!historyStarted) {
      historyStarted = true;
      pageCursor = executions.at(-1)?.id || null;
      hasMore = executions.length === pageSize;
    }
    mergeExecutions(executions);
    updateHistoryNavigation();
  } catch {
    if (generation !== historyGeneration) return;
    State.runtimeReady = false;
    $('#submitMission').disabled = true;
    $('#runtimeStatus').textContent =
      'Sin conexión con el runtime local. Pulsa RECONECTAR cuando la API esté disponible.';
  } finally {
    if (refreshing === generation) refreshing = null;
  }
}

async function syncRuntime() {
  if (runtimeRefreshing === historyGeneration) return;
  const generation = historyGeneration;
  runtimeRefreshing = generation;
  try {
    const runtime = await fetchApi('/api/runtime');
    if (generation !== historyGeneration) return;
    State.runtimeReady = runtime.ready;
    State.monitorOnly = Boolean(runtime.monitor_only);
    document.querySelectorAll('[data-mission-control]').forEach((node) => {
      node.hidden = State.monitorOnly;
    });
    $('#missionForm').hidden = State.monitorOnly;
    $('#executionHistory').hidden = State.monitorOnly;
    if (!$('#runtimeWorkspace').value) {
      $('#runtimeWorkspace').value =
        State.monitorWorkspace || (State.monitorOnly ? '' : runtime.workspace);
      if (State.monitorOnly)
        $('#runtimeWorkspace').placeholder = `Automático: ${runtime.workspace}`;
    }
    $('#runtimeStatus').textContent = runtime.message;
    $('#submitMission').disabled = !runtime.ready || State.executionBusy || !missionAllowed();
    if (!State.monitorOnly) await syncExecutions();
    else {
      const navigation = $('#loadOlderExecutions');
      if (navigation) navigation.hidden = true;
    }
  } catch (error) {
    if (generation !== historyGeneration) return;
    State.runtimeReady = false;
    $('#submitMission').disabled = true;
    $('#runtimeStatus').textContent = `Codex no disponible: ${error.message}`;
  } finally {
    if (runtimeRefreshing === generation) runtimeRefreshing = null;
  }
}

function startExecutions() {
  $('#submitMission').disabled = true;
  $('#refreshRuntime').addEventListener('click', syncRuntime);
  $('#runtimeWorkspace').addEventListener('change', () => {
    selectMonitorWorkspace($('#runtimeWorkspace').value.trim());
  });
  $('#monitorProjectSelect').addEventListener('change', (event) => {
    $('#runtimeWorkspace').value = event.target.value;
    selectMonitorWorkspace(event.target.value);
  });
  syncRuntime();
  setInterval(() => {
    if (!State.monitorOnly) syncExecutions();
  }, 2000);
  setInterval(() => {
    if (!State.runtimeReady) syncRuntime();
  }, 15000);
}

function selectMonitorWorkspace(workspace) {
  State.monitorWorkspace = workspace;
  localStorage.setItem('slimeops-workspace', workspace);
  $('#monitorProjectSelect').value = workspace;
  resetLiveContext();
  connectLiveStream();
  syncDashboard().catch(() => {});
}

export {
  startExecutions,
  syncExecutions,
  syncRuntime,
  resetExecutionHistory,
  renderExecutions,
  missionAllowed,
};
