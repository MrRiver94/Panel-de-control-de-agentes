import { visualStatus } from '../agents/model.js';
import { BreakActivities, RoomStations, WorkActionCycle } from '../config.js';
import { $, uppercase } from '../dom.js';
import { State } from '../state.js';
import { applyRoomCamera } from './camera.js';

function createSlimeUnit(agent) {
  const unit = document.createElement('div');
  unit.className = 'SlimeUnit';
  unit.dataset.agentId = agent.id;
  unit.innerHTML =
    '<i class="AgentStateBeacon" aria-hidden="true"></i><i class="WorkLabel"></i><i class="ActionProp" aria-hidden="true"></i><i class="SlimeSprite" aria-hidden="true"></i><strong></strong>';
  return unit;
}

function updateSlimeUnit(element, agent) {
  const commuting = agent.visualPhase === 'commuting';
  const [x, y] = agent.position || agent.sleep;
  const restPose = agent.restActivity
    ? ''
    : agent.roomZone === 'rest'
      ? agent.idle_mode === 'Sleep'
        ? 'Sleep'
        : agent.idle_mode || 'Coffee'
      : agent.idle_mode;
  const stateClass = commuting
    ? `Commuting ${agent.idle_mode}`
    : agent.status === 'working' || agent.simulatedWorking
      ? `Working WorkAction${uppercase(agent.workAction || 'typing')}`
      : `Resting ${restPose}${agent.moving ? ' Moving' : ''}`;
  const status = visualStatus(agent);
  element.className = `SlimeUnit ${stateClass} Status${uppercase(status[0])}${status.slice(1)}${agent.restActivity && !agent.moving ? ` Using${uppercase(agent.restActivity[0])}${agent.restActivity.slice(1)}` : ''}`;
  element.dataset.break = agent.restActivity || BreakActivities[agent.id] || 'coffee';
  element.dataset.workAction = agent.workAction || 'typing';
  element.style.setProperty('--tone', agent.tone);
  element.style.setProperty('--hue', agent.hue || '0deg');
  element.style.left = `calc(${x}% - 29px)`;
  element.style.top = `calc(${y}% - 62px)`;
  element.style.zIndex = String(5 + Math.round(y));
  const action = WorkActionCycle.find((item) => item.id === agent.workAction);
  const label = commuting
    ? 'en ruta'
    : agent.restActivity === 'stroll'
      ? 'paseando'
      : agent.restActivity === 'eating'
        ? 'comiendo'
        : agent.restActivity === 'coffee'
          ? 'tomando café'
          : agent.roomZone === 'rest'
            ? 'durmiendo'
            : status === 'error'
              ? 'error'
              : action?.label || agent.action;
  element.querySelector('.WorkLabel').textContent = label;
  element.querySelector('.ActionProp').dataset.glyph = action?.glyph || '';
  element.querySelector('strong').textContent = agent.name;
}

function renderSlimeRoom() {
  const world = $('#roomWorld');
  adjustRestLayoutForViewport(world);
  applyRoomCamera(world);
  const ids = new Set(State.agents.map((agent) => agent.id));
  const current = new Map();
  world.querySelectorAll('[data-agent-id]').forEach((element) => {
    const id = element.dataset.agentId;
    if (!ids.has(id) || current.has(id)) element.remove();
    else current.set(id, element);
  });
  State.agents.forEach((agent) => {
    let element = current.get(agent.id);
    if (!element) {
      element = createSlimeUnit(agent);
      world.append(element);
    }
    updateSlimeUnit(element, agent);
  });
  const errors = State.agents
    .filter((agent) => visualStatus(agent) === 'error')
    .map((agent) => agent.name);
  const activeNames = State.agents
    .filter((agent) => agent.status === 'working' && visualStatus(agent) !== 'error')
    .map((agent) => agent.name);
  $('#roomStatus').textContent = State.roomSimulation
    ? 'SIMULACIÓN VISUAL · TODOS AL TRABAJO'
    : errors.length
      ? `ALERTA: ${errors.join(' + ')}`
      : activeNames.length
        ? activeNames.join(' + ')
        : 'Todos descansando';
}

function adjustRestLayoutForViewport(world) {
  const compact = world.clientWidth < 430;
  const mobileSlots = [
    [5, 35],
    [17, 35],
    [29, 35],
    [5, 56],
    [17, 56],
    [29, 56],
  ];
  State.agents.forEach((agent, index) => {
    const point = compact ? mobileSlots[index % mobileSlots.length] : RoomStations[agent.id]?.rest;
    if (point) agent.homeRest = [...point];
    if (agent.route || agent.roomZone !== 'rest' || Boolean(agent.mobileRestSlot) === compact)
      return;
    if (!point) return;
    agent.position = [...point];
    agent.sleep = [...point];
    agent.mobileRestSlot = compact;
  });
}

export { createSlimeUnit, updateSlimeUnit, renderSlimeRoom, adjustRestLayoutForViewport };
