import { RoomStations } from '../config.js';
import { restoreRoomAgent } from '../room/storage.js';
import { State } from '../state.js';

const getSelectedAgent = () => State.agents.find((agent) => agent.id === State.selectedAgentId);

function buildVisualAgent(remote) {
  const stations = Object.values(RoomStations);
  const station = RoomStations[remote.id] || stations[State.agents.length % stations.length];
  return restoreRoomAgent({
    ...remote,
    hue: remote.display_hue || '0deg',
    sleep: [...station.rest],
    work: [...station.desk],
    position: [...station.rest],
    roomZone: 'rest',
    action: remote.default_action || 'en espera',
    visualPhase: undefined,
  });
}

function visualStatus(agent) {
  return agent.simulatedWorking
    ? 'running'
    : agent.operationalStatus || (agent.status === 'working' ? 'running' : 'standby');
}

function agentStateLabel(agent) {
  if (agent.visualPhase === 'commuting') return 'EN RUTA';
  if (agent.simulatedWorking) return 'SIMULANDO';
  return (
    {
      active: 'ACTIVO',
      running: 'TRABAJANDO',
      thinking: 'PENSANDO',
      paused: 'EN PAUSA',
      blocked: 'RECARGANDO',
      error: 'ERROR',
      standby: 'DESCANSANDO',
    }[visualStatus(agent)] || 'DESCANSANDO'
  );
}

function agentActivityCopy(agent) {
  if (agent.simulatedWorking)
    return agent.visualPhase === 'commuting'
      ? 'Recorrido de prueba hacia el despacho. No se ha creado ninguna misión.'
      : 'En su puesto durante la simulación visual. No se consumen tokens.';
  if (agent.visualPhase === 'commuting') return `Va hacia su puesto para ${agent.action}.`;
  if (visualStatus(agent) === 'thinking')
    return 'El backend indica que está pensando. Su pantalla parpadea hasta recibir un nuevo estado.';
  if (visualStatus(agent) === 'error')
    return 'El backend ha marcado un error. Revisa la consola de eventos para conocer el detalle.';
  if (visualStatus(agent) === 'blocked')
    return 'Ha alcanzado un bloqueo o límite de uso y está recargando.';
  if (visualStatus(agent) === 'paused') return 'Está en pausa por indicación del backend.';
  if (agent.status === 'working') return `Está en su estación: ${agent.action}.`;
  return 'Está en la sala común, disponible para la siguiente misión.';
}

export { getSelectedAgent, buildVisualAgent, visualStatus, agentStateLabel, agentActivityCopy };
