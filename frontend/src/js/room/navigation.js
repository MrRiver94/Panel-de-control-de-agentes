import { LoungeVisits, RoomStations, WorkActionCycle } from '../config.js';
import { $ } from '../dom.js';
import { State } from '../state.js';
import { isRoomPointWalkable } from './geometry.js';
import { updateSlimeUnit } from './render.js';

function routeToRoom(agent, zone) {
  if (agent.route) {
    agent.nextRoomZone = zone;
    return;
  }
  if (agent.roomZone === zone) return;
  const station =
    RoomStations[agent.id] ||
    Object.values(RoomStations)[State.agents.indexOf(agent) % Object.keys(RoomStations).length];
  const start = [...(agent.position || (zone === 'work' ? agent.sleep : agent.work))];
  const destination = zone === 'work' ? agent.work : station.rest;
  const caveMouth = [35, 47];
  const meadowEntry = [44, 49];
  const restLaneY = agent.position?.[1] < 45 ? 44 : 55;
  if (zone === 'work') agent.restActivity = undefined;
  agent.route =
    zone === 'work'
      ? [
          start,
          [start[0], restLaneY],
          [30, restLaneY],
          [35, 47],
          caveMouth,
          meadowEntry,
          [49, 51],
          [station.fieldLane[0], 51],
          [...station.fieldLane],
          [...destination],
        ]
      : [
          start,
          [...station.fieldLane],
          [station.fieldLane[0], 51],
          [49, 51],
          meadowEntry,
          caveMouth,
          [35, 47],
          [30, restLaneY],
          [destination[0], restLaneY],
          [...destination],
        ];
  agent.routeIndex = 0;
  agent.segmentStart = Date.now();
  agent.routeTarget = zone;
  agent.visualPhase = 'commuting';
  agent.moving = true;
}

function advanceRoomRoutes() {
  const now = Date.now();
  const world = $('#roomWorld');
  const frameElapsed = Math.min(250, Math.max(0, now - (State.lastRoomFrameAt || now)));
  State.lastRoomFrameAt = now;
  State.agents.forEach((agent) => {
    if (!agent.route) return;
    // Wall-clock time lets a route catch up after reload or a backgrounded tab.
    for (let step = 0; agent.route && step < 24; step++) {
      const start = agent.route[agent.routeIndex];
      const end = agent.route[agent.routeIndex + 1];
      const distance = Math.hypot(end[0] - start[0], end[1] - start[1]);
      const duration = Math.max(300, distance * 115);
      const progress = Math.max(0, Math.min(1, (now - agent.segmentStart) / duration));
      const previousPosition = agent.position || start;
      const candidate = [
        start[0] + (end[0] - start[0]) * progress,
        start[1] + (end[1] - start[1]) * progress,
      ];
      const blockedByWall = !isRoomPointWalkable(candidate);
      if (blockedByWall) {
        agent.position = [...previousPosition];
        agent.segmentStart += frameElapsed;
        break;
      }
      agent.position = candidate;
      if (progress < 1) break;
      agent.routeIndex += 1;
      agent.segmentStart += duration;
      if (agent.routeIndex === agent.route.length - 1) {
        agent.roomZone = agent.routeTarget;
        if (agent.roomZone === 'rest') {
          agent.restUntil = now + 12000 + Math.random() * 6000;
          agent.restActivity = undefined;
        }
        agent.route = null;
        agent.moving = false;
        agent.visualPhase = agent.roomZone === 'work' ? 'working' : undefined;
        const nextZone = agent.nextRoomZone;
        agent.nextRoomZone = undefined;
        if (nextZone && nextZone !== agent.roomZone) routeToRoom(agent, nextZone);
      }
    }
    const element = world.querySelector(`[data-agent-id="${agent.id}"]`);
    if (element) updateSlimeUnit(element, agent);
  });
  requestAnimationFrame(advanceRoomRoutes);
}

function makeSlimesWander() {
  if (State.roomSimulation) return;
  const now = Date.now();
  State.agents
    .filter(
      (agent) =>
        agent.status !== 'working' &&
        !agent.route &&
        agent.roomZone === 'rest' &&
        now >= (agent.restUntil || 0),
    )
    .forEach((agent) => {
      const restChoice = Math.random();
      if (agent.id === 'director' && !agent.coffeeBreakShown) {
        agent.coffeeBreakShown = true;
        agent.restActivity = 'coffee';
        agent.restUntil = now + 9000;
        return;
      }
      if (restChoice < 0.31) {
        agent.restActivity = 'eating';
        agent.restUntil = now + 6500 + Math.random() * 4500;
        return;
      }
      if (restChoice < 0.64) {
        agent.restActivity = 'coffee';
        agent.restUntil = now + 7500 + Math.random() * 5000;
        return;
      }
      agent.loungeStep = ((agent.loungeStep ?? 0) + 1) % LoungeVisits.length;
      const offset = LoungeVisits[agent.loungeStep];
      const anchor = agent.homeRest || RoomStations[agent.id]?.rest || agent.sleep || [18, 55];
      let point = [
        Math.max(2, Math.min(27, anchor[0] + offset[0])),
        Math.max(18, Math.min(60, anchor[1] + offset[1])),
      ];
      if (!isRoomPointWalkable(point)) point = [...anchor];
      agent.restActivity = 'stroll';
      agent.sleep = [...point];
      agent.route = [[...(agent.position || anchor)], [...point]];
      agent.routeIndex = 0;
      agent.segmentStart = now;
      agent.routeTarget = 'rest';
      agent.moving = true;
    });
}

function cycleWorkActions() {
  State.agents.forEach((agent, index) => {
    if (agent.status !== 'working' && !agent.simulatedWorking) return;
    if ((agent.execution_id || agent.usage_source === 'codex-external') && !agent.simulatedWorking)
      return;
    const current = WorkActionCycle.findIndex((action) => action.id === agent.workAction);
    const next = (current + 1 + (index % 3)) % WorkActionCycle.length;
    agent.workAction = WorkActionCycle[next].id;
    const element = document.querySelector(`[data-agent-id="${agent.id}"]`);
    if (element) updateSlimeUnit(element, agent);
  });
}

export { routeToRoom, advanceRoomRoutes, makeSlimesWander, cycleWorkActions };
