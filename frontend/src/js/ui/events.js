import { getSelectedAgent } from '../agents/model.js';
import { $ } from '../dom.js';
import { openAuditHistory } from '../features/activity.js';
import { renderAgentWatchPanels } from '../features/agent-watch.js';
import {
  getControlDraft,
  modelsFor,
  openCustomizer,
  previewCustomizer,
  renderControlPanel,
  renderCustomizer,
  saveAgentControls,
  saveCustomizer,
} from '../features/controls.js';
import { submitMission } from '../features/missions.js';
import { controlRoomCamera } from '../room/camera.js';
import { syncCodexUsage } from '../services/live.js';
import { State } from '../state.js';

function bindInteractions() {
  $('#agentSelect').addEventListener('change', (event) => {
    State.selectedAgentId = event.target.value;
    $('#controlFeedback').textContent = '';
    renderControlPanel();
  });
  $('#budgetInput').addEventListener('input', (event) => {
    const draft = getControlDraft(getSelectedAgent());
    draft.token_budget = Number(event.target.value);
    draft.dirty = true;
  });
  $('#providerSelect').addEventListener('change', (event) => {
    const draft = getControlDraft(getSelectedAgent());
    draft.provider = event.target.value;
    draft.model = modelsFor(draft.provider)[0] || '';
    draft.dirty = true;
    renderControlPanel();
  });
  $('#modelSelect').addEventListener('change', (event) => {
    const draft = getControlDraft(getSelectedAgent());
    draft.model = event.target.value;
    draft.dirty = true;
  });
  $('#effortSelector').addEventListener('click', (event) => {
    const level = event.target.dataset.effort;
    if (!level) return;
    const draft = getControlDraft(getSelectedAgent());
    draft.reasoning_effort = level;
    draft.dirty = true;
    renderControlPanel();
  });
  $('#saveControls').addEventListener('click', saveAgentControls);
  $('#openCustomizer').addEventListener('click', openCustomizer);
  $('#closeCustomizer').addEventListener('click', () => $('#customizerDialog').close());
  $('#cancelCustomizer').addEventListener('click', () => $('#customizerDialog').close());
  $('#customizerForm').addEventListener('submit', saveCustomizer);
  $('#profileAgentSelect').addEventListener('change', (event) => {
    State.profileAgentId = event.target.value;
    renderCustomizer();
  });
  [
    'profileName',
    'profileRole',
    'profileAction',
    'profileTone',
    'profileHue',
    'profileActions',
  ].forEach((id) => $(`#${id}`).addEventListener('input', previewCustomizer));
  $('#missionForm').addEventListener('submit', submitMission);
  $('#refreshCodexUsage').addEventListener('click', () => syncCodexUsage().catch(() => {}));
  $('#openAudit').addEventListener('click', () => openAuditHistory());
  $('#closeAudit').addEventListener('click', () => $('#auditDialog').close());
  document.querySelector('.LiveOpsLayout').addEventListener('click', (event) => {
    const camera = event.target.closest('[data-camera]');
    if (camera) {
      controlRoomCamera(camera.dataset.camera);
      return;
    }
    const button = event.target.closest('[data-agent-info]');
    if (!button) return;
    const id = button.dataset.agentInfo;
    State.openAgentId = State.openAgentId === id ? null : id;
    renderAgentWatchPanels();
  });
}

export { bindInteractions };
