import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';

const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const setup = source.slice(0, source.lastIndexOf('bindInteractions(); bindAccess();'));

function openRoom(storage = new Map()) {
  const world = {querySelector: () => null};
  const button = {textContent:'', addEventListener() {}, classList:{add() {}, remove() {}}};
  const feed = {scrollHeight:0, scrollTop:0, clientHeight:0, children:[], replaceChildren(...children) { this.children = children; }};
  const count = {textContent:''};
  const context = {
    structuredClone, Date, Intl, Math, Number, JSON, Object, Array, Map, Set,
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value)
    },
    document: {
      addEventListener() {}, createElement: () => ({className:'', textContent:''}),
      querySelector: (selector) => ({'#terminalFeed':feed, '#terminalCount':count})[selector] || (selector === '#simulateAll' ? button : world)
    },
    requestAnimationFrame() {}
  };
  runInNewContext(`${setup}\nrenderDashboard = () => {}; renderSlimeRoom = () => {}; updateConnectionLabel = () => {}; globalThis.room = {State, routeToRoom, advanceRoomRoutes, saveRoomState, consumeDashboard, triggerWorkAnimation, startRoomSimulation, stopRoomSimulation, agentStateLabel, renderTerminal};`, context);
  context.room.feed = feed;
  context.room.terminalCount = count;
  return context.room;
}

test('a reload resumes an in-progress commute and catches up after time away', () => {
  const storage = new Map();
  const first = openRoom(storage);
  const agent = first.State.agents[0];
  first.routeToRoom(agent, 'work');
  agent.segmentStart -= 800;
  first.advanceRoomRoutes();
  const position = [...agent.position];
  assert.ok(agent.route);
  first.saveRoomState();

  const reopened = openRoom(storage);
  const restored = reopened.State.agents[0];
  assert.equal(restored.roomStateRestored, true);
  assert.equal(restored.routeTarget, 'work');
  assert.deepEqual([...restored.position], position);
  restored.segmentStart -= 60_000;
  reopened.advanceRoomRoutes();
  assert.equal(restored.roomZone, 'work');
  assert.equal(restored.route, null);
  assert.deepEqual([...restored.position], [...restored.work]);
});

test('an already-running agent appears at its desk on first connection', () => {
  const room = openRoom();
  room.consumeDashboard({agents:[{id:'director', status:'running', current_task:'En espera'}], events:[]});
  const agent = room.State.agents[0];
  assert.equal(agent.roomZone, 'work');
  assert.equal(agent.route, undefined);
  assert.deepEqual([...agent.position], [...agent.work]);
});

test('a new mission still starts a fresh route from the lounge', () => {
  const room = openRoom();
  room.consumeDashboard({agents:[{id:'director', status:'idle', current_task:'En espera'}], events:[]});
  room.triggerWorkAnimation(['director']);
  const agent = room.State.agents[0];
  assert.equal(agent.routeTarget, 'work');
  assert.equal(agent.visualPhase, 'commuting');
});

test('visual simulation survives API updates and restores the live room without dispatching', () => {
  const storage = new Map();
  const room = openRoom(storage);
  const dashboard = {agents:[{id:'director', status:'idle', current_task:'En espera'}], events:[]};
  room.consumeDashboard(dashboard);
  const agent = room.State.agents[0];
  const original = [...agent.position];
  room.startRoomSimulation();
  assert.equal(agent.routeTarget, 'work');
  assert.equal(agent.simulatedWorking, true);
  const savedBefore = storage.get('slimeops-room-v6');
  room.consumeDashboard(dashboard);
  room.saveRoomState();
  assert.equal(agent.routeTarget, 'work');
  assert.equal(storage.get('slimeops-room-v6'), savedBefore);
  room.stopRoomSimulation();
  assert.equal(room.State.roomSimulation, null);
  assert.equal(agent.simulatedWorking, undefined);
  assert.deepEqual([...agent.position], original);
});

test('backend thinking, error and paused states drive distinct visual states', () => {
  const room = openRoom();
  const snapshot = (status) => ({agents:[{id:'scout', status, current_task:'Investigando'}], events:[]});
  room.consumeDashboard(snapshot('thinking'));
  const agent = room.State.agents[0];
  assert.equal(agent.status, 'working');
  assert.equal(room.agentStateLabel(agent), 'PENSANDO');
  room.consumeDashboard(snapshot('error'));
  assert.equal(room.agentStateLabel(agent), 'ERROR');
  room.consumeDashboard(snapshot('paused'));
  assert.equal(agent.status, 'sleeping');
  agent.segmentStart -= 60_000;
  room.advanceRoomRoutes();
  assert.equal(room.agentStateLabel(agent), 'EN PAUSA');
});

test('terminal renders all event messages as text in chronological order', () => {
  const room = openRoom();
  room.State.events = [
    {id:'new', agent:'SCOUT', kind:'status_error', message:'<script>unsafe</script>', created_at:'2026-10-23T11:00:00Z'},
    {id:'old', agent:'NEXUS', kind:'mission_dispatched', message:'Delegado', created_at:'2026-10-23T10:59:00Z'}
  ];
  room.renderTerminal();
  assert.equal(room.feed.children.length, 2);
  assert.match(room.feed.children[0].textContent, /NEXUS/);
  assert.match(room.feed.children[1].textContent, /<script>unsafe<\/script>/);
  assert.equal(room.feed.children[1].className, 'TerminalLine IsError');
  assert.equal(room.terminalCount.textContent, '2 REGISTROS');
});
