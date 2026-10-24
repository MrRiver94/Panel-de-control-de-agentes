import { $ } from '../dom.js';
import { routeToRoom } from '../room/navigation.js';
import { renderSlimeRoom } from '../room/render.js';
import { stopRoomSimulation } from '../room/simulation.js';
import { fetchApi } from '../services/api.js';
import { State } from '../state.js';
import { renderDashboard } from '../ui/dashboard.js';

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
  const dispatches = events.filter((event) => event.kind === 'mission_dispatched');
  if (!State.dashboardReady) {
    dispatches.forEach((event) => State.knownDispatches.add(event.id));
    State.dashboardReady = true;
    return;
  }
  const agentIds = dispatches
    .filter((event) => !State.knownDispatches.has(event.id))
    .map((event) => {
      State.knownDispatches.add(event.id);
      return State.agents.find((agent) => agent.name === event.agent)?.id;
    })
    .filter(Boolean);
  if (!State.roomSimulation) triggerWorkAnimation([...new Set(agentIds)]);
}

function localRouteMission(prompt) {
  const value = prompt.toLowerCase();
  const selected = ['director', 'nexus'];
  if (/investiga|fuente|busca|compet|analiza/.test(value)) selected.push('scout');
  if (/crea|constru|código|codigo|web|diseña|disena/.test(value)) selected.push('forge');
  if (/revisa|calidad|error|test|riesgo/.test(value)) selected.push('sentinel');
  if (
    /diseñ|disen|visual|estética|estetica|ui|ux|pixel|anim|ilustración|ilustracion|arte|estilo|interfaz|layout|escenario|paisaje|ilumina|luces|luz|sprite|vegetación|vegetacion|árbol|arbol/.test(
      value,
    )
  )
    selected.push('muse');
  return [...new Set(selected.length === 2 ? [...selected, 'scout'] : selected)];
}

async function submitMission(event) {
  event.preventDefault();
  const input = $('#missionInput');
  const prompt = input.value.trim();
  if (!prompt) return;
  if (State.roomSimulation) stopRoomSimulation();
  let assigned = localRouteMission(prompt);
  State.agents.forEach((agent) => {
    if (!assigned.includes(agent.id)) {
      agent.status = 'sleeping';
      routeToRoom(agent, 'rest');
    }
  });
  triggerWorkAnimation(assigned);
  $('#missionSummary').textContent = 'Trabajo iniciado. Los slimes van hacia su despacho…';
  input.value = '';
  renderDashboard();
  try {
    const result = await fetchApi('/api/dispatch', {
      method: 'POST',
      body: JSON.stringify({ prompt }),
    });
    assigned = result.agent_ids;
    triggerWorkAnimation(assigned);
    $('#missionSummary').textContent = result.plan;
  } catch {
    $('#missionSummary').textContent = 'Misión iniciada en modo demo.';
  }
}

export { triggerWorkAnimation, detectRemoteDispatches, localRouteMission, submitMission };
