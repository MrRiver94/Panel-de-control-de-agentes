import { State } from '../../src/js/state.js';
import { renderAccess, bindAccess } from '../../src/js/features/access.js';
import {
  renderControlPanel,
  renderCustomizer,
  saveCustomizer,
} from '../../src/js/features/controls.js';
import { renderAgentWatchPanels } from '../../src/js/features/agent-watch.js';
import { renderSlimeRoom } from '../../src/js/room/render.js';
import {
  renderExecutions,
  syncExecutions,
  syncRuntime,
  resetExecutionHistory,
  missionAllowed,
} from '../../src/js/features/executions.js';
import { refreshLocalMonitor } from '../../src/js/features/sessions.js';

const results = [];
const $ = (selector) => document.querySelector(selector);
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};
const response = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const agent = (id) => ({
  id,
  name: id,
  role: 'Especialista',
  tone: '#79e8ee',
  hue: '0deg',
  status: 'sleeping',
  operationalStatus: 'standby',
  position: [15, 35],
  sleep: [15, 35],
  work: [80, 25],
  roomZone: 'rest',
  idle_mode: 'Coffee',
  action: 'En espera',
  default_action: 'En espera',
  enabled_actions: ['coordinar'],
  reasoning_effort: 'medium',
  token_budget: 5000,
  tokens_used: 0,
});
const execution = (id, status = 'completed') => ({
  id,
  status,
  prompt: `Misión ${id}`,
  workspace: 'C:/proyecto',
  sandbox: 'workspace-write',
  created_at: `2026-10-26T12:${String(id).padStart(2, '0')}:00Z`,
  changed_files: ['app.py'],
  steps: [{ name: 'FORGE', status: 'completed', effort: 'medium', has_result: true }],
});
async function check(name, callback) {
  try {
    await callback();
    results.push({ name, ok: true });
  } catch (error) {
    results.push({ name, ok: false, error: error.stack || error.message });
  }
}
async function waitFor(callback) {
  for (let i = 0; i < 50; i++) {
    if (callback()) return;
    await tick();
  }
  throw new Error('La actualización del DOM no terminó.');
}

try {
  window.fetch = async () => {
    throw new Error('Una prueba intentó acceder a la red.');
  };
  State.operatorId = 'super-admin';
  State.agents = [agent('custom')];
  State.selectedAgentId = 'custom';
  State.profileAgentId = 'custom';
  await check('access renders stored HTML and IDs as literal text', async () => {
    const html = '<img src=x onerror="window.__xss=true">';
    State.access = {
      roles: [{ id: 'super-admin', name: html, permissions: ['*', html] }],
      users: [{ id: 'super-admin', name: html, role_id: 'super-admin' }],
    };
    State.agents[0].name = html;
    State.agents[0].role = html;
    renderAccess();
    renderControlPanel();
    renderCustomizer();
    await tick();
    assert(
      !$('#accessTree').querySelector('img,script') &&
        !$('#accessActions').querySelector('img,script'),
      'Se interpretó HTML guardado.',
    );
    assert(
      $('#accessTree').textContent.includes(html),
      'El nombre/permisos no se conservaron literalmente.',
    );
    assert(
      $('#activeUserSelect').options[0].text === html,
      'El selector de usuarios perdió el texto literal.',
    );
    assert(
      $('#agentSelect').options[0].text.includes(html),
      'El selector de agentes no conserva texto.',
    );
    assert(!window.__xss, 'Se ejecutó el manejador inyectado.');
  });
  await check('new users and roles immediately receive CRUD actions', async () => {
    bindAccess();
    const tree = structuredClone(State.access);
    tree.roles.push({ id: 'reviewer', name: 'Revisor', permissions: ['dashboard.view'] });
    window.fetch = async (url) => {
      assert(String(url).endsWith('/api/access/roles'), 'Ruta de alta de rol inesperada.');
      return response(tree);
    };
    $('#newRoleName').value = 'Revisor';
    $('#newRolePermissions').value = 'dashboard.view';
    $('#roleForm').dispatchEvent(new Event('submit', { cancelable: true }));
    await waitFor(() => !!document.querySelector('[data-role-edit="reviewer"]'));
    tree.users.push({ id: 'viewer', name: 'Lector', role_id: 'reviewer' });
    window.fetch = async (url) => {
      assert(String(url).endsWith('/api/access/users'), 'Ruta de alta de usuario inesperada.');
      return response(tree);
    };
    $('#newUserName').value = 'Lector';
    $('#newUserRole').value = 'reviewer';
    $('#userForm').dispatchEvent(new Event('submit', { cancelable: true }));
    await waitFor(() => !!document.querySelector('[data-user-delete="viewer"]'));
    renderAccess();
    assert(document.querySelectorAll('#accessActions').length === 1, 'Se duplicó la sección CRUD.');
  });
  await check(
    'agent additions, deletions and rail moves keep exactly one node per ID',
    async () => {
      State.agents = Array.from({ length: 6 }, (_, index) => agent(`agent-${index}`));
      renderAgentWatchPanels();
      renderSlimeRoom();
      const fourth = [...document.querySelectorAll('[data-watch-agent-id]')].find(
        (node) => node.dataset.watchAgentId === 'agent-3',
      );
      assert(
        fourth.parentElement.id === 'agentWatchRailRight',
        'El escenario no comienza en el lateral derecho.',
      );
      State.agents.push(agent('unsafe" data-injected="true'));
      renderAgentWatchPanels();
      renderSlimeRoom();
      assert(
        fourth.parentElement.id === 'agentWatchRailLeft',
        'La tarjeta no se trasladó entre laterales.',
      );
      assert(
        document.querySelectorAll('[data-watch-agent-id]').length === 7,
        'Se duplicaron tarjetas al cambiar de lateral.',
      );
      assert(!document.querySelector('[data-injected]'), 'Se interpoló un ID como HTML.');
      State.agents.splice(3, 1);
      renderAgentWatchPanels();
      renderSlimeRoom();
      assert(!fourth.isConnected, 'La tarjeta borrada sigue en el DOM.');
      assert(
        document.querySelectorAll('[data-agent-id]').length === 6,
        'El slime borrado sigue en la sala.',
      );
    },
  );
  await check(
    'rejected profile edits preserve the form draft without mutating confirmed state',
    async () => {
      State.agents = [agent('custom')];
      State.selectedAgentId = 'custom';
      State.profileAgentId = 'custom';
      renderCustomizer();
      $('#profileName').value = 'Borrador nuevo';
      window.fetch = async () => response({ detail: 'Permission required: agents.update' }, 403);
      await saveCustomizer({ preventDefault() {} });
      assert(State.agents[0].name === 'custom', 'El rechazo alteró el estado confirmado.');
      assert($('#profileName').value === 'Borrador nuevo', 'Se perdió el borrador del formulario.');
      assert(
        $('#customizerHint').textContent.includes('No se guardó'),
        'El rechazo se presentó como guardado.',
      );
      window.fetch = async (url, options) =>
        response({ ...State.agents[0], ...JSON.parse(options.body) });
      await saveCustomizer({ preventDefault() {} });
      assert(State.agents[0].name === 'Borrador nuevo', 'El reintento confirmado no se publicó.');
    },
  );
  await check('runtime refresh preserves mission permissions for a limited operator', async () => {
    const access = State.access;
    State.access = {
      roles: [{ id: 'viewer', name: 'Lector', permissions: ['dashboard.view'] }],
      users: [{ id: 'viewer', name: 'Lector', role_id: 'viewer' }],
    };
    State.operatorId = 'viewer';
    resetExecutionHistory();
    window.fetch = async (url) =>
      String(url).endsWith('/api/runtime')
        ? response({ ready: true, message: 'Codex disponible', workspace: 'C:/proyecto' })
        : response([]);
    await syncRuntime();
    assert($('#submitMission').disabled, 'El refresco del runtime anuló el permiso de misión.');
    renderExecutions([execution('01', 'failed')]);
    assert(
      document.querySelector('.ExecutionRecord button').disabled,
      'Se permitió reintentar sin permiso.',
    );
    renderExecutions([execution('01', 'running')]);
    assert(
      document.querySelector('.ExecutionRecord button').disabled,
      'Se permitió cancelar sin permiso.',
    );
    State.access = null;
    renderExecutions([]);
    assert(
      !$('#submitMission').disabled,
      'Se bloqueó el modo local antes de cargar los permisos del servidor.',
    );
    State.access = access;
    State.operatorId = 'super-admin';
    resetExecutionHistory();
  });
  await check('polling preserves loaded diff, result nodes, expansion and selection', async () => {
    resetExecutionHistory();
    State.runtimeReady = true;
    const old = execution('01');
    const active = execution('02', 'running');
    renderExecutions([active, old]);
    const record = document.querySelector('[data-id="01"]');
    record.open = true;
    window.fetch = async (url) =>
      String(url).endsWith('/diff')
        ? response({ files: [{ path: 'app.py', patch: '+ contenido que debe permanecer' }] })
        : response({ ...old, steps: [{ name: 'FORGE', result: 'Resultado que debe permanecer' }] });
    record.querySelector('.ExecutionDiff button').click();
    record.querySelector('.ExecutionResults button').click();
    await waitFor(() => !!record.querySelector('.ExecutionResults pre'));
    const patch = record.querySelector('.ExecutionDiff pre');
    const result = record.querySelector('.ExecutionResults pre');
    const detail = record.querySelector('.ExecutionDiff details');
    detail.open = true;
    const range = document.createRange();
    range.selectNodeContents(patch);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
    const selected = window.getSelection().toString();
    renderExecutions([
      { ...active, outcome: 'Progreso nuevo' },
      { ...old, outcome: 'Metadatos actualizados' },
    ]);
    assert(
      record === document.querySelector('[data-id="01"]') && record.open && detail.open,
      'Se reemplazó el registro o su expansión.',
    );
    assert(
      patch === record.querySelector('.ExecutionDiff pre') &&
        result === record.querySelector('.ExecutionResults pre'),
      'Se descartaron resultados/diffs descargados.',
    );
    assert(
      window.getSelection().toString() === selected,
      'Se perdió la selección durante el refresco.',
    );
  });
  await check(
    'history cursor retains all older records when a new mission is inserted',
    async () => {
      resetExecutionHistory();
      State.runtimeReady = true;
      const dataset = Array.from({ length: 26 }, (_, i) => execution(String(40 - i)));
      const calls = [];
      window.fetch = async (url) => {
        const query = new URL(url).searchParams;
        const before = query.get('before');
        calls.push(before || 'first');
        assert(query.get('limit') === '20', 'No se limitó la página solicitada.');
        assert(!query.has('offset'), 'La paginación utiliza un offset inestable.');
        const start = before ? dataset.findIndex((item) => item.id === before) + 1 : 0;
        return response(dataset.slice(start, start + 20));
      };
      await syncExecutions();
      const initial = document.querySelector('[data-id="40"]');
      initial.open = true;
      dataset.unshift(execution('41'));
      await syncExecutions();
      $('#loadOlderExecutions').click();
      await waitFor(() => document.querySelectorAll('.ExecutionRecord').length === 27);
      assert(calls.join(',') === 'first,first,21', 'El cursor de página es incorrecto.');
      assert(
        dataset.every((item) =>
          [...document.querySelectorAll('.ExecutionRecord')].some(
            (node) => node.dataset.id === item.id,
          ),
        ),
        'La inserción omitió una misión anterior.',
      );
      assert(
        initial === document.querySelector('[data-id="40"]') && initial.open,
        'La paginación reemplazó un registro abierto.',
      );
      assert($('#loadOlderExecutions').hidden, 'Se ofrecen páginas después del final.');
      await syncExecutions();
      assert(
        document.querySelectorAll('.ExecutionRecord').length === 27,
        'El refresco perdió las páginas antiguas.',
      );
    },
  );
  await check('local diagnostics preserve manual projects and render paths as text', async () => {
    const path = 'C:/project/<img src=x onerror=alert(1)>';
    State.monitorWorkspace = 'C:/manual-project';
    window.fetch = async () =>
      response({
        message: 'Monitor leyendo actividad local',
        account: { message: 'CLI no disponible; sesiones locales legibles' },
        sessions_directory: path,
        projects: [{ name: '<img src=x>', workspace: path }],
      });
    await refreshLocalMonitor();
    assert($('#localMonitorDirectory').textContent.includes(path), 'La ruta perdió su contenido.');
    assert(
      !$('#localMonitorDirectory').querySelector('img'),
      'Se interpretó HTML en el diagnóstico.',
    );
    assert(
      $('#monitorProjectSelect').options.length === 3,
      'Faltan la selección automática, el proyecto detectado o el manual.',
    );
    assert(
      $('#monitorProjectSelect').value === State.monitorWorkspace,
      'Se perdió el proyecto manual.',
    );
    State.monitorWorkspace = '';
  });
  await check(
    'monitor mode hides mission controls and never requests execution history',
    async () => {
      let historyRequests = 0;
      window.fetch = async (url) => {
        if (String(url).includes('/api/runtime'))
          return response({
            ready: false,
            monitor_only: true,
            workspace: 'C:/latest',
            message: 'Monitor activo',
          });
        historyRequests += 1;
        return response([]);
      };
      $('#runtimeWorkspace').value = '';
      await syncRuntime();
      assert(State.monitorOnly && !missionAllowed(), 'El modo monitor permite enviar misiones.');
      assert(
        $('#missionForm').hidden && $('#executionHistory').hidden,
        'Se muestran controles de ejecución.',
      );
      assert(
        [...document.querySelectorAll('[data-mission-control]')].every((node) => node.hidden),
        'Se muestran permisos de escritura.',
      );
      assert(
        $('#submitMission').disabled && historyRequests === 0,
        'El monitor consultó ejecuciones o activó el envío.',
      );
      window.fetch = async (url) =>
        response(
          String(url).includes('/api/runtime')
            ? {
                ready: true,
                monitor_only: false,
                workspace: 'C:/project',
                message: 'Codex conectado',
              }
            : [],
        );
      await syncRuntime();
      assert(
        !$('#missionForm').hidden && !State.monitorOnly,
        'No se restauró el modo de ejecución adicional.',
      );
    },
  );
  await check('changing operator discards an outstanding history response', async () => {
    resetExecutionHistory();
    let resolve;
    window.fetch = () =>
      new Promise((done) => {
        resolve = done;
      });
    const pending = syncExecutions();
    State.operatorId = 'viewer';
    resetExecutionHistory();
    let refreshedCurrentOperator = false;
    window.fetch = async () => {
      refreshedCurrentOperator = true;
      return response([]);
    };
    await syncExecutions();
    assert(
      refreshedCurrentOperator,
      'La consulta anterior bloqueó el refresco del operador nuevo.',
    );
    resolve(response([execution('01')]));
    await pending;
    assert(
      !document.querySelector('.ExecutionRecord'),
      'La respuesta del operador anterior volvió a mostrar su historial.',
    );
  });
} catch (error) {
  results.push({ name: 'browser fixture setup', ok: false, error: error.stack || error.message });
}
document.documentElement.dataset.regression = encodeURIComponent(JSON.stringify(results));
