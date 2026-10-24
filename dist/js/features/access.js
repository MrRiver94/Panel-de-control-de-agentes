import { buildVisualAgent, getSelectedAgent } from '../agents/model.js';
import { DemoAgents } from '../config.js';
import { $ } from '../dom.js';
import { fetchApi } from '../services/api.js';
import { syncDashboard } from '../services/live.js';
import { State } from '../state.js';
import { renderDashboard } from '../ui/dashboard.js';

function applyAccess() {
  const role = State.access?.roles.find(
    (item) => item.id === State.access?.users.find((item) => item.id === State.operatorId)?.role_id,
  );
  const permissions = role?.permissions || [];
  const allowed = (permission) => permissions.includes('*') || permissions.includes(permission);
  $('#saveControls').disabled = !allowed('agents.update');
  $('#openCustomizer').disabled = !allowed('agents.update');
  $('#missionForm button').disabled = !allowed('mission.create');
  $('#openAccess').style.display = allowed('access.manage') ? '' : 'none';
}

function renderAccess() {
  const tree = State.access;
  if (!tree) return;
  $('#activeUserSelect').innerHTML = tree.users
    .map((user) => `<option value="${user.id}">${user.name}</option>`)
    .join('');
  $('#activeUserSelect').value = State.operatorId;
  $('#newUserRole').innerHTML = tree.roles
    .map((role) => `<option value="${role.id}">${role.name}</option>`)
    .join('');
  $('#accessTree').innerHTML = tree.roles
    .map(
      (role) =>
        `<section><b>${role.name}</b><small>${role.permissions.join(' · ')}</small>${
          tree.users
            .filter((user) => user.role_id === role.id)
            .map((user) => `<p>└ ${user.name}</p>`)
            .join('') || '<p>└ sin usuarios</p>'
        }</section>`,
    )
    .join('');
  applyAccess();
}

async function openAccess() {
  try {
    State.access = await fetchApi('/api/access/tree');
    renderAccess();
    renderAccessActions();
    $('#accessDialog').showModal();
  } catch {
    alert('No tienes permiso para gestionar accesos.');
  }
}

function renderAccessActions() {
  const tree = State.access;
  if (!tree || $('#accessActions')) return;
  const roleCards = tree.roles
    .map(
      (role) =>
        `<div class="AccessRow"><span>ROL: ${role.name}</span>${role.id === 'super-admin' ? '<small>PROTEGIDO</small>' : `<button data-role-edit="${role.id}">EDITAR</button><button data-role-delete="${role.id}">BORRAR</button>`}</div>`,
    )
    .join('');
  const userCards = tree.users
    .map(
      (user) =>
        `<div class="AccessRow"><span>USUARIO: ${user.name}</span>${user.id === 'super-admin' ? '<small>PROTEGIDO</small>' : `<button data-user-edit="${user.id}">EDITAR</button><button data-user-delete="${user.id}">BORRAR</button>`}</div>`,
    )
    .join('');
  const selected = getSelectedAgent();
  const agentAction =
    selected && !DemoAgents.some((agent) => agent.id === selected.id)
      ? `<button class="SecondaryButton" data-agent-delete="${selected.id}">ELIMINAR ${selected.name}</button>`
      : '';
  $('#accessTree').insertAdjacentHTML(
    'afterend',
    `<section class="AccessActions" id="accessActions"><button class="PrimaryButton" id="openCreateAgent" type="button">+ CREAR AGENTE</button>${agentAction}<h3>GESTIÓN CRUD</h3>${roleCards}${userCards}</section>`,
  );
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
        refreshAccessActions();
      }
      if (button.dataset.roleDelete && confirm('¿Eliminar este rol?')) {
        State.access = await fetchApi(`/api/access/roles/${button.dataset.roleDelete}`, {
          method: 'DELETE',
        });
        renderAccess();
        refreshAccessActions();
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
        refreshAccessActions();
      }
      if (button.dataset.userDelete && confirm('¿Eliminar este usuario?')) {
        State.access = await fetchApi(`/api/access/users/${button.dataset.userDelete}`, {
          method: 'DELETE',
        });
        renderAccess();
        refreshAccessActions();
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
    renderAccess();
    syncDashboard().catch(() => {});
  });
  $('#roleForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = $('#newRoleName').value.trim();
    const permissions = $('#newRolePermissions')
      .value.split(',')
      .map((item) => item.trim())
      .filter(Boolean);
    if (!name || !permissions.length) return;
    State.access = await fetchApi('/api/access/roles', {
      method: 'POST',
      body: JSON.stringify({ name, permissions }),
    });
    renderAccess();
  });
  $('#userForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = $('#newUserName').value.trim();
    if (!name) return;
    State.access = await fetchApi('/api/access/users', {
      method: 'POST',
      body: JSON.stringify({ name, role_id: $('#newUserRole').value }),
    });
    renderAccess();
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
