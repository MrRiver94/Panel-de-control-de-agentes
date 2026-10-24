import { getSelectedAgent } from '../agents/model.js';
import { EffortLevels, FallbackModelCatalog } from '../config.js';
import { $, uppercase } from '../dom.js';
import { fetchApi } from '../services/api.js';
import { State } from '../state.js';
import { renderDashboard } from '../ui/dashboard.js';

function getControlDraft(agent) {
  const current = State.controlDrafts.get(agent.id);
  if (current?.dirty) return current;
  const fresh = {
    token_budget: agent.token_budget,
    reasoning_effort: agent.reasoning_effort,
    provider: agent.provider || 'codex',
    model: agent.model || '',
    dirty: false,
  };
  State.controlDrafts.set(agent.id, fresh);
  return fresh;
}

function modelsFor(provider) {
  return State.modelCatalog.providers.find((item) => item.id === provider)?.models || [];
}

function renderControlPanel() {
  const agent = getSelectedAgent();
  const draft = getControlDraft(agent);
  $('#agentSelect').innerHTML = State.agents
    .map((item) => `<option value="${item.id}">${item.name} — ${item.role}</option>`)
    .join('');
  $('#agentSelect').value = agent.id;
  $('#budgetInput').value = draft.token_budget;
  const providers = $('#providerSelect');
  providers.replaceChildren(
    ...State.modelCatalog.providers.map((item) => new Option(item.label, item.id)),
  );
  providers.value = draft.provider;
  const modelSelect = $('#modelSelect');
  const models = [...modelsFor(draft.provider)];
  if (draft.model && !models.includes(draft.model)) models.unshift(draft.model);
  modelSelect.replaceChildren(
    new Option('Sin asignar', ''),
    ...models.map((model) => new Option(model, model)),
  );
  modelSelect.value = draft.model;
  $('#modelHint').textContent =
    State.modelCatalog.source === 'configured'
      ? 'Modelos recibidos de la configuración de la API.'
      : 'Modelos sugeridos; la disponibilidad depende de tu cuenta. Sin asignar utiliza el modelo de Codex local. Presupuesto orientativo por fase.';
  $('#effortSelector').innerHTML = EffortLevels.map(
    (level) =>
      `<button class="EffortButton ${draft.reasoning_effort === level ? 'Active' : ''}" data-effort="${level}">${uppercase(level)}</button>`,
  ).join('');
}

async function syncModelCatalog() {
  try {
    const catalog = await fetchApi('/api/models');
    if (Array.isArray(catalog.providers) && catalog.providers.length) State.modelCatalog = catalog;
  } catch {
    State.modelCatalog = FallbackModelCatalog;
  }
  renderControlPanel();
}

function getProfileAgent() {
  return State.agents.find((agent) => agent.id === State.profileAgentId) || getSelectedAgent();
}

function renderCustomizer() {
  const agent = getProfileAgent();
  $('#profileAgentSelect').innerHTML = State.agents
    .map((item) => `<option value="${item.id}">${item.name} — ${item.role}</option>`)
    .join('');
  $('#profileAgentSelect').value = agent.id;
  $('#profileName').value = agent.name;
  $('#profileRole').value = agent.role;
  $('#profileAction').value = agent.default_action || agent.action;
  $('#profileTone').value = agent.tone;
  $('#profileHue').value = agent.display_hue || agent.hue || '0deg';
  $('#profileIdle').value = agent.idle_mode || 'Coffee';
  document.querySelectorAll('#profileActions input').forEach((input) => {
    input.checked = (agent.enabled_actions || []).includes(input.value);
  });
  $('#previewName').textContent = agent.name;
  $('#previewRole').textContent = agent.role;
  $('#previewActions').textContent = (agent.enabled_actions || []).join(' · ').toUpperCase();
  $('#previewSlime').style.setProperty('--preview-tone', agent.tone);
  $('#previewSlime').style.setProperty('--preview-hue', agent.display_hue || agent.hue || '0deg');
}

function openCustomizer() {
  State.profileAgentId = State.selectedAgentId;
  renderCustomizer();
  $('#customizerDialog').showModal();
}

function previewCustomizer() {
  const agent = getProfileAgent();
  const selectedActions = [...document.querySelectorAll('#profileActions input:checked')].map(
    (input) => input.value,
  );
  $('#previewName').textContent = $('#profileName').value || agent.name;
  $('#previewRole').textContent = $('#profileRole').value || agent.role;
  $('#previewActions').textContent = selectedActions.join(' · ').toUpperCase() || 'SIN ACCIONES';
  $('#previewSlime').style.setProperty('--preview-tone', $('#profileTone').value);
  $('#previewSlime').style.setProperty('--preview-hue', $('#profileHue').value);
}

async function saveCustomizer(event) {
  event.preventDefault();
  const agent = getProfileAgent();
  const enabled_actions = [...document.querySelectorAll('#profileActions input:checked')].map(
    (input) => input.value,
  );
  if (!enabled_actions.length) {
    $('#customizerHint').textContent = 'Selecciona al menos una acción.';
    return;
  }
  const profile = {
    name: $('#profileName').value.trim(),
    role: $('#profileRole').value.trim(),
    default_action: $('#profileAction').value.trim(),
    tone: $('#profileTone').value,
    display_hue: $('#profileHue').value,
    idle_mode: $('#profileIdle').value,
    enabled_actions,
  };
  if (!profile.name || !profile.role || !profile.default_action) return;
  Object.assign(agent, profile, { hue: profile.display_hue, action: profile.default_action });
  try {
    const updated = await fetchApi(`/api/agents/${agent.id}/profile`, {
      method: 'POST',
      body: JSON.stringify(profile),
    });
    Object.assign(agent, updated, { hue: updated.display_hue, action: updated.default_action });
    $('#customizerHint').textContent = 'Perfil guardado y auditado.';
    renderDashboard();
    setTimeout(() => $('#customizerDialog').close(), 450);
  } catch {
    $('#customizerHint').textContent = 'Guardado local: conecta la API para persistirlo.';
    renderDashboard();
  }
}

async function saveAgentControls() {
  const agent = getSelectedAgent();
  const { dirty, ...draft } = getControlDraft(agent);
  draft.token_budget = Number($('#budgetInput').value);
  if (draft.token_budget < 500 || draft.token_budget > 24000) {
    $('#controlFeedback').textContent = 'El límite debe estar entre 500 y 24.000 tokens.';
    return;
  }
  try {
    const updated = await fetchApi(`/api/agents/${agent.id}/controls`, {
      method: 'POST',
      body: JSON.stringify(draft),
    });
    Object.assign(agent, updated);
    State.controlDrafts.delete(agent.id);
    $('#controlFeedback').textContent =
      `${agent.provider} · ${agent.model || 'sin modelo'} guardado.`;
  } catch (error) {
    if (!State.connected) {
      Object.assign(agent, draft);
      State.controlDrafts.delete(agent.id);
      $('#controlFeedback').textContent = 'Ajuste solo local: conecta la API para guardarlo.';
    } else {
      $('#controlFeedback').textContent = `No se guardó: ${error.message}`;
    }
  }
  renderDashboard();
}

export {
  getControlDraft,
  modelsFor,
  renderControlPanel,
  syncModelCatalog,
  getProfileAgent,
  renderCustomizer,
  openCustomizer,
  previewCustomizer,
  saveCustomizer,
  saveAgentControls,
};
