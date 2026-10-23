import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';

const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const setup = source.slice(0, source.lastIndexOf('bindInteractions(); bindAccess();'));

function openRoom(storage = new Map()) {
  const world = {querySelector: () => null};
  const context = {
    structuredClone, Date, Intl, Math, Number, JSON, Object, Array, Map, Set,
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value)
    },
    document: {addEventListener() {}, querySelector: () => world},
    requestAnimationFrame() {}
  };
  runInNewContext(`${setup}\nrenderDashboard = () => {}; renderSlimeRoom = () => {}; updateConnectionLabel = () => {}; globalThis.room = {State, routeToRoom, advanceRoomRoutes, saveRoomState, consumeDashboard, triggerWorkAnimation};`, context);
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
