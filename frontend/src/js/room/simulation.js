import { RoomStations, RoomVisualFields } from '../config.js';
import { $ } from '../dom.js';
import { consumeDashboard } from '../services/live.js';
import { State } from '../state.js';
import { renderDashboard } from '../ui/dashboard.js';
import { routeToRoom } from './navigation.js';
import { saveRoomState } from './storage.js';

function startRoomSimulation() {
  if (State.roomSimulation || !State.agents.length) return;
  saveRoomState();
  State.roomSimulation = new Map(
    State.agents.map((agent) => {
      const visual = Object.fromEntries(RoomVisualFields.map((field) => [field, agent[field]]));
      return [agent.id, structuredClone(visual)];
    }),
  );
  State.agents.forEach((agent) => {
    const station =
      RoomStations[agent.id] ||
      Object.values(RoomStations)[State.agents.indexOf(agent) % Object.keys(RoomStations).length];
    agent.route = null;
    agent.nextRoomZone = undefined;
    agent.position = [...(agent.homeRest || station.rest)];
    agent.sleep = [...(agent.homeRest || station.rest)];
    agent.roomZone = 'rest';
    agent.simulatedWorking = true;
    routeToRoom(agent, 'work');
  });
  const button = $('#simulateAll');
  button.textContent = 'VOLVER AL DIRECTO';
  button.classList.add('IsRunning');
  renderDashboard();
}

function stopRoomSimulation() {
  if (!State.roomSimulation) return;
  State.agents.forEach((agent) => {
    const previous = State.roomSimulation.get(agent.id);
    if (previous)
      RoomVisualFields.forEach((field) => {
        if (previous[field] === undefined) delete agent[field];
        else agent[field] = previous[field];
      });
    delete agent.simulatedWorking;
  });
  State.roomSimulation = null;
  const button = $('#simulateAll');
  button.textContent = 'SIMULAR: TODOS AL TRABAJO';
  button.classList.remove('IsRunning');
  if (State.latestDashboard) consumeDashboard(State.latestDashboard, { replay: true });
  else renderDashboard();
  saveRoomState();
}

export { startRoomSimulation, stopRoomSimulation };
