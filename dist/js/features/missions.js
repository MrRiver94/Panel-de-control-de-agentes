import { $ } from '../dom.js';
import { routeToRoom } from '../room/navigation.js';
import { renderSlimeRoom } from '../room/render.js';
import { stopRoomSimulation } from '../room/simulation.js';
import { fetchApi } from '../services/api.js';
import { State } from '../state.js';
import { renderDashboard } from '../ui/dashboard.js';
import { syncExecutions } from './executions.js';

function triggerWorkAnimation(agentIds) {
  State.agents
    .filter((agent) => agentIds.includes(agent.id))
    .forEach((agent) => {
      agent.status = 'working';
      agent.operationalStatus = 'running';
      routeToRoom(agent, 'work');
    });
  renderSlimeRoom();
}

function detectRemoteDispatches(events) {
  // The dashboard's operational status is authoritative, including completed turns.
  events
    .filter((event) => event.kind === 'mission_dispatched')
    .forEach((event) => State.knownDispatches.add(event.id));
  State.dashboardReady = true;
}

async function submitMission(event) {
  event.preventDefault();
  const input = $('#missionInput');
  const prompt = input.value.trim();
  if (prompt.length < 3 || !State.runtimeReady || State.executionBusy) return;
  if (State.roomSimulation) stopRoomSimulation();
  const button = $('#submitMission');
  button.disabled = true;
  State.executionBusy = true;
  $('#missionSummary').textContent = 'Solicitando ejecución a Codex…';
  const payload = {
    prompt,
    workspace: $('#runtimeWorkspace').value.trim() || null,
    sandbox: $('#runtimeSandbox').value,
    planning: $('#runtimePlanning').value,
  };
  const key = JSON.stringify(payload);
  if (State.pendingDispatch?.key !== key) State.pendingDispatch = { key, id: crypto.randomUUID() };
  try {
    const result = await fetchApi('/api/dispatch', {
      method: 'POST',
      body: JSON.stringify({ ...payload, request_id: State.pendingDispatch.id }),
    });
    input.value = '';
    State.pendingDispatch = null;
    $('#missionSummary').textContent = result.plan;
    await syncExecutions();
  } catch (error) {
    State.executionBusy = false;
    button.disabled = false;
    $('#missionSummary').textContent = `No se inició la misión: ${error.message}`;
  }
}

export { triggerWorkAnimation, detectRemoteDispatches, submitMission };
