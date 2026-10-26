import { buildVisualAgent, getSelectedAgent } from '../agents/model.js';
import { DemoAgents } from '../config.js';
import { $, textElement } from '../dom.js';
import { fetchApi } from '../services/api.js';
import { syncDashboard, connectLiveStream, resetLiveContext } from '../services/live.js';
import { State } from '../state.js';
import { renderDashboard } from '../ui/dashboard.js';
import { resetExecutionHistory, syncRuntime, missionAllowed } from './executions.js';

function applyAccess() {
  const role = State.access?.roles.find(
    (item) => item.id === State.access?.users.find((item) => item.id === State.operatorId)?.role_id,
  );
  const permissions = role?.permissions || [];
  const allowed = (permission) => permissions.includes('*') || permissions.includes(permission);
  $('#saveControls').disabled = !allowed('agents.update');
  $('#openCustomizer').disabled = !allowed('agents.update');
  $('#missionForm button').disabled =
    !missionAllowed() || !State.runtimeReady || State.executionBusy;
  $('#openAccess').style.display = allowed('access.manage') ? '' : 'none';
}

function renderAccess() {
  const tree = State.access;
  if (!tree) return;
  $('#activeUserSelect').replaceChildren(
    ...tree.users.map((user) => new Option(user.name, user.id)),
  );
  $('#activeUserSelect').value = State.operatorId;
  $('#newUserRole').replaceChildren(...tree.roles.map((role) => new Option(role.name, role.id)));
  $('#accessTree').replaceChildren(
    ...tree.roles.map((role) => {
      const section = document.createElement('section');
      section.append(
        textElement('b', role.name),
        textElement('small', role.permissions.join(' · ')),
      );
      const users = tree.users.filter((user) => user.role_id === role.id);
      section.append(
        ...(users.length
          ? users.map((user) => textElement('p', `└ ${user.name}`))
          : [textElement('p', '└ sin usuarios')]),
      );
      return section;
    }),
  );
  renderAccessActions();
  applyAccess();
}

async function openAccess() {
  try {
    State.access = await fetchApi('/api/access/tree');
    renderAccess();
    $('#accessDialog').showModal();
  } catch {
    alert('No tienes permiso para gestionar accesos.');
  }
}

function renderAccessActions() {
  const tree = State.access;
  if (!tree) return;
  let actions = $('#accessActions');
  if (!actions) {
    actions = document.createElement('section');
    actions.className = 'AccessActions';
    actions.id = 'accessActions';
    $('#accessTree').after(actions);
  }
  const create = textElement('button', '+ CREAR AGENTE');
  create.type = 'button';
  create.className = 'PrimaryButton';
  create.id = 'openCreateAgent';
  actions.replaceChildren(create);
  const selected = getSelectedAgent();
  if (selected && !DemoAgents.some((agent) => agent.id === selected.id)) {
    const remove = textElement('button', `ELIMINAR ${selected.name}`);
    remove.type = 'button';
    remove.className = 'SecondaryButton';
    remove.dataset.agentDelete = selected.id;
    actions.append(remove);
  }
  actions.append(textElement('h3', 'GESTIÓN CRUD'));
  for (const [kind, label, records] of [
    ['role', 'ROL', tree.roles],
    ['user', 'USUARIO', tree.users],
  ]) {
    for (const record of records) {
      const row = document.createElement('div');
      row.className = 'AccessRow';
      row.append(textElement('span', `${label}: ${record.name}`));
      if (record.id === 'super-admin') row.append(textElement('small', 'PROTEGIDO'));
      else
        for (const [action, title] of [
          ['Edit', 'EDITAR'],
          ['Delete', 'BORRAR'],
        ]) {
          const button = textElement('button', title);
          button.type = 'button';
          button.dataset[kind + action] = record.id;
          row.append(button);
        }
      actions.append(row);
    }
  }
}

function refreshAccessActions() {
  $('#accessActions')?.remove();
  renderAccessActions();
}

function selectedCreateActions() {
  return [...document.querySelectorAll('#createAgentActions input:checked')].map(
    (input) => input.value,
  );
}

function bindAgentCreation() {
  $('#accessDialog').addEventListener('click', async (event) => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.id === 'openCreateAgent') {
      $('#createAgentDialog').showModal();
      return;
    }
    try {
      if (button.dataset.roleEdit) {
        const role = State.access.roles.find((item) => item.id === button.dataset.roleEdit);
        const name = prompt('Nombre del rol', role.name);
        if (!name) return;
        const permissions = prompt('Permisos separados por coma', role.permissions.join(','));
        if (!permissions) return;
        State.access = await fetchApi(`/api/access/roles/${role.id}`, {
          method: 'POST',
          body: JSON.stringify({
            name,
            permissions: permissions
              .split(',')
              .map((item) => item.trim())
              .filter(Boolean),
          }),
        });
        renderAccess();
      }
      if (button.dataset.roleDelete && confirm('¿Eliminar este rol?')) {
        State.access = await fetchApi(`/api/access/roles/${button.dataset.roleDelete}`, {
          method: 'DELETE',
        });
        renderAccess();
      }
      if (button.dataset.userEdit) {
        const user = State.access.users.find((item) => item.id === button.dataset.userEdit);
        const name = prompt('Nombre del usuario', user.name);
        if (!name) return;
        const role_id = prompt(
          `Rol (${State.access.roles.map((role) => role.id).join(', ')})`,
          user.role_id,
        );
        if (!role_id) return;
        State.access = await fetchApi(`/api/access/users/${user.id}`, {
          method: 'POST',
          body: JSON.stringify({ name, role_id }),
        });
        renderAccess();
      }
      if (button.dataset.userDelete && confirm('¿Eliminar este usuario?')) {
        State.access = await fetchApi(`/api/access/users/${button.dataset.userDelete}`, {
          method: 'DELETE',
        });
        renderAccess();
      }
    } catch (error) {
      alert(`No se pudo guardar: ${error.message}`);
    }
  });
  $('#closeCreateAgent').addEventListener('click', () => $('#createAgentDialog').close());
  $('#createAgentForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const enabled_actions = selectedCreateActions();
    if (!enabled_actions.length) return;
    const payload = {
      name: $('#createAgentName').value.trim(),
      role: $('#createAgentRole').value.trim(),
      tone: $('#createAgentTone').value,
      display_hue: '0deg',
      idle_mode: $('#createAgentIdle').value,
      default_action: $('#createAgentAction').value.trim(),
      enabled_actions,
      token_budget: Number($('#createAgentBudget').value),
      reasoning_effort: $('#createAgentEffort').value,
    };
    try {
      const created = await fetchApi('/api/agents', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      State.agents.push(buildVisualAgent(created));
      State.selectedAgentId = created.id;
      renderDashboard();
      refreshAccessActions();
      $('#createAgentDialog').close();
    } catch (error) {
      alert(`No se pudo crear el agente: ${error.message}`);
    }
  });
}

function bindAccess() {
  $('#openAccess').addEventListener('click', openAccess);
  $('#closeAccess').addEventListener('click', () => $('#accessDialog').close());
  $('#activeUserSelect').addEventListener('change', (event) => {
    State.operatorId = event.target.value;
    localStorage.setItem('slimeops-operator', State.operatorId);
    resetLiveContext();
    resetExecutionHistory();
    renderAccess();
    connectLiveStream();
    syncDashboard().catch(() => {});
    syncRuntime();
  });
  $('#roleForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = $('#newRoleName').value.trim();
    const permissions = $('#newRolePermissions')
      .value.split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    if (!name || !permissions.length) return;
    try {
      State.access = await fetchApi('/api/access/roles', {
        method: 'POST',
        body: JSON.stringify({ name, permissions }),
      });
      renderAccess();
    } catch (error) {
      alert(`No se pudo crear el rol: ${error.message}`);
    }
  });
  $('#userForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = $('#newUserName').value.trim();
    if (!name) return;
    try {
      State.access = await fetchApi('/api/access/users', {
        method: 'POST',
        body: JSON.stringify({ name, role_id: $('#newUserRole').value }),
      });
      renderAccess();
    } catch (error) {
      alert(`No se pudo crear el usuario: ${error.message}`);
    }
  });
}

function bindAgentDeletion() {
  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-agent-delete]');
    if (!button || !confirm(`Eliminar ${button.dataset.agentDelete}?`)) return;
    try {
      await fetchApi(`/api/agents/${button.dataset.agentDelete}`, { method: 'DELETE' });
      State.agents = State.agents.filter((agent) => agent.id !== button.dataset.agentDelete);
      State.selectedAgentId = State.agents[0]?.id;
      refreshAccessActions();
      renderDashboard();
    } catch (error) {
      alert(`No se pudo eliminar: ${error.message}`);
    }
  });
}

export {
  applyAccess,
  renderAccess,
  openAccess,
  renderAccessActions,
  refreshAccessActions,
  selectedCreateActions,
  bindAgentCreation,
  bindAccess,
  bindAgentDeletion,
};
