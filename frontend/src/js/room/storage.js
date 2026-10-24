import { RestActivities, RoomStateKey } from '../config.js';
import { State } from '../state.js';

const validPoint = (point) =>
  Array.isArray(point) &&
  point.length === 2 &&
  point.every((value) => Number.isFinite(value) && value >= 0 && value <= 100);

function readRoomState() {
  try {
    const saved = JSON.parse(localStorage.getItem(RoomStateKey));
    return saved?.savedAt > Date.now() - 86400000 &&
      saved?.savedAt <= Date.now() &&
      saved.agents &&
      typeof saved.agents === 'object'
      ? saved.agents
      : {};
  } catch {
    return {};
  }
}

const SavedRoomAgents = readRoomState();

function restoreRoomAgent(agent) {
  const saved = SavedRoomAgents[agent.id];
  if (!saved || !validPoint(saved.position) || !['rest', 'work'].includes(saved.roomZone))
    return agent;
  agent.position = [...saved.position];
  agent.roomZone = saved.roomZone;
  agent.status = saved.status === 'working' ? 'working' : 'sleeping';
  agent.visualPhase =
    saved.visualPhase === 'commuting'
      ? 'commuting'
      : agent.roomZone === 'work'
        ? 'working'
        : undefined;
  agent.loungeStep = Number.isInteger(saved.loungeStep) ? saved.loungeStep : undefined;
  agent.restUntil =
    Number.isFinite(saved.restUntil) && saved.restUntil > Date.now() ? saved.restUntil : undefined;
  agent.restActivity = RestActivities.has(saved.restActivity) ? saved.restActivity : undefined;
  if (validPoint(saved.sleep)) agent.sleep = [...saved.sleep];
  if (
    Array.isArray(saved.route) &&
    saved.route.length >= 2 &&
    saved.route.length <= 12 &&
    saved.route.every(validPoint) &&
    Number.isInteger(saved.routeIndex) &&
    saved.routeIndex >= 0 &&
    saved.routeIndex < saved.route.length - 1 &&
    Number.isFinite(saved.segmentStart) &&
    saved.segmentStart <= Date.now() &&
    ['rest', 'work'].includes(saved.routeTarget)
  ) {
    agent.route = saved.route.map((point) => [...point]);
    agent.routeIndex = saved.routeIndex;
    agent.segmentStart = saved.segmentStart;
    agent.routeTarget = saved.routeTarget;
    agent.nextRoomZone = ['rest', 'work'].includes(saved.nextRoomZone)
      ? saved.nextRoomZone
      : undefined;
    agent.visualPhase = saved.visualPhase === 'commuting' ? 'commuting' : undefined;
    agent.moving = true;
  }
  agent.roomStateRestored = true;
  return agent;
}

function saveRoomState() {
  if (State.roomSimulation) return;
  try {
    const agents = Object.fromEntries(
      State.agents.map((agent) => [
        agent.id,
        {
          position: agent.position,
          sleep: agent.sleep,
          roomZone: agent.roomZone,
          status: agent.status,
          visualPhase: agent.visualPhase,
          loungeStep: agent.loungeStep,
          route: agent.route,
          routeIndex: agent.routeIndex,
          segmentStart: agent.segmentStart,
          routeTarget: agent.routeTarget,
          nextRoomZone: agent.nextRoomZone,
          restUntil: agent.restUntil,
          restActivity: agent.restActivity,
        },
      ]),
    );
    localStorage.setItem(RoomStateKey, JSON.stringify({ savedAt: Date.now(), agents }));
  } catch {
    /* Storage can be unavailable in private browsing. */
  }
}

export { validPoint, readRoomState, SavedRoomAgents, restoreRoomAgent, saveRoomState };
