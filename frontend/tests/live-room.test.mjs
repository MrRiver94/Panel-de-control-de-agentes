import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { SourceTextModule, SyntheticModule, createContext } from 'node:vm';
import { fileURLToPath } from 'node:url';
import { resolve, dirname } from 'node:path';

const sourceDirectory = fileURLToPath(new URL('../src/', import.meta.url));

async function openRoom(storage = new Map()) {
  const properties = new Map();
  const world = {
    querySelector: () => null,
    style: { setProperty: (name, value) => properties.set(name, value) },
  };
  const cameras = ['out', 'left', 'up', 'center', 'down', 'right', 'in'].map((command) => ({
    dataset: { camera: command },
    disabled: false,
  }));
  const button = { textContent: '', addEventListener() {}, classList: { add() {}, remove() {} } };
  const feed = {
    scrollHeight: 0,
    scrollTop: 0,
    clientHeight: 0,
    children: [],
    replaceChildren(...children) {
      this.children = children;
    },
  };
  const count = { textContent: '' };
  const context = {
    structuredClone,
    Date,
    Intl,
    Math,
    Number,
    JSON,
    Object,
    Array,
    Map,
    Set,
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
    },
    document: {
      querySelectorAll: () => cameras,
      addEventListener() {},
      createElement: () => ({ className: '', textContent: '' }),
      querySelector: (selector) =>
        ({ '#terminalFeed': feed, '#terminalCount': count })[selector] ||
        (selector === '#simulateAll' ? button : world),
    },
    requestAnimationFrame() {},
  };
  const sandbox = createContext(context);
  const modules = new Map();
  const overrides = {
    'js/ui/dashboard.js': ['renderDashboard', 'updateConnectionLabel', 'updateDigitalClock'],
    'js/room/render.js': [
      'renderSlimeRoom',
      'updateSlimeUnit',
      'adjustRestLayoutForViewport',
      'createSlimeUnit',
    ],
  };
  function load(filename) {
    if (modules.has(filename)) return modules.get(filename);
    const key = filename.slice(sourceDirectory.length).replaceAll('\\', '/');
    let module;
    if (overrides[key]) {
      const names = overrides[key];
      module = new SyntheticModule(
        names,
        function () {
          for (const name of names) this.setExport(name, () => {});
        },
        { context: sandbox, identifier: filename },
      );
    } else
      module = new SourceTextModule(readFileSync(filename, 'utf8'), {
        context: sandbox,
        identifier: filename,
      });
    modules.set(filename, module);
    return module;
  }
  const entry = new SourceTextModule(
    `
    import { State } from './js/state.js';
    import { RoomStateKey } from './js/config.js';
    import { restoreRoomAgent,saveRoomState } from './js/room/storage.js';
    import { routeToRoom,advanceRoomRoutes } from './js/room/navigation.js';
    import { consumeDashboard } from './js/services/live.js';
    import { triggerWorkAnimation } from './js/features/missions.js';
    import { startRoomSimulation,stopRoomSimulation } from './js/room/simulation.js';
    import { agentStateLabel } from './js/agents/model.js';
    import { renderTerminal } from './js/features/activity.js';
    import { controlRoomCamera,applyRoomCamera,roomCameraPose } from './js/room/camera.js';
    State.agents.forEach(restoreRoomAgent);
    globalThis.room = {State,RoomStateKey,routeToRoom,advanceRoomRoutes,saveRoomState,consumeDashboard,triggerWorkAnimation,startRoomSimulation,stopRoomSimulation,agentStateLabel,renderTerminal,controlRoomCamera,applyRoomCamera,roomCameraPose};
  `,
    { context: sandbox, identifier: resolve(sourceDirectory, 'test-entry.js') },
  );
  await entry.link((specifier, parent) => load(resolve(dirname(parent.identifier), specifier)));
  await entry.evaluate();
  context.room.feed = feed;
  context.room.terminalCount = count;
  context.room.world = world;
  context.room.properties = properties;
  context.room.cameras = cameras;
  return context.room;
}

test('camera arrows move the view in their named direction', async () => {
  const room = await openRoom();
  room.State.roomZoom = 2;
  for (const [command, axis, expected] of [
    ['right', '--room-pan-x', '-5%'],
    ['left', '--room-pan-x', '5%'],
    ['down', '--room-pan-y', '-5%'],
    ['up', '--room-pan-y', '5%'],
  ]) {
    room.State.roomPan = 0;
    room.State.roomPanY = 0;
    room.controlRoomCamera(command);
    room.applyRoomCamera(room.world);
    assert.equal(room.properties.get(axis), expected);
  }
});

test('camera never exposes space outside the map through repeated pan and zoom operations', async () => {
  const room = await openRoom();
  const commands = [
    ...Array(10).fill('in'),
    ...Array(25).fill('right'),
    ...Array(25).fill('up'),
    ...Array(10).fill('out'),
    ...Array(20).fill('left'),
    ...Array(20).fill('down'),
  ];
  for (const command of commands) {
    room.controlRoomCamera(command);
    const { roomZoom: zoom, roomPan: x, roomPanY: y } = room.State;
    assert.ok(zoom >= 1 && zoom <= 2.4);
    for (const offset of [x, y]) {
      assert.ok(50 * (1 - zoom) - offset <= 1e-8);
      assert.ok(50 * (1 + zoom) - offset >= 100 - 1e-8);
    }
  }
  room.applyRoomCamera(room.world);
  for (const button of room.cameras.filter((item) =>
    ['out', 'left', 'right', 'up', 'down'].includes(item.dataset.camera),
  ))
    assert.equal(button.disabled, true);
});

test('view all restores the full map and neutralizes pan at minimum zoom', async () => {
  const room = await openRoom();
  room.State.roomZoom = 2.4;
  room.State.roomPan = 60;
  room.State.roomPanY = -40;
  room.controlRoomCamera('center');
  assert.equal(room.State.roomZoom, 1);
  assert.equal(room.State.roomPan, 0);
  assert.equal(room.State.roomPanY, 0);
  room.controlRoomCamera('left');
  room.controlRoomCamera('up');
  room.controlRoomCamera('out');
  assert.equal(room.State.roomZoom, 1);
  assert.equal(room.State.roomPan, 0);
  assert.equal(room.State.roomPanY, 0);
});

test('a reload resumes an in-progress commute and catches up after time away', async () => {
  const storage = new Map();
  const first = await openRoom(storage);
  const agent = first.State.agents[0];
  first.routeToRoom(agent, 'work');
  agent.segmentStart -= 800;
  first.advanceRoomRoutes();
  const position = [...agent.position];
  assert.ok(agent.route);
  first.saveRoomState();

  const reopened = await openRoom(storage);
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

test('an already-running agent appears at its desk on first connection', async () => {
  const room = await openRoom();
  room.consumeDashboard({
    agents: [{ id: 'director', status: 'running', current_task: 'En espera' }],
    events: [],
  });
  const agent = room.State.agents[0];
  assert.equal(agent.roomZone, 'work');
  assert.equal(agent.route, undefined);
  assert.deepEqual([...agent.position], [...agent.work]);
});

test('a new mission still starts a fresh route from the lounge', async () => {
  const room = await openRoom();
  room.consumeDashboard({
    agents: [{ id: 'director', status: 'idle', current_task: 'En espera' }],
    events: [],
  });
  room.triggerWorkAnimation(['director']);
  const agent = room.State.agents[0];
  assert.equal(agent.routeTarget, 'work');
  assert.equal(agent.visualPhase, 'commuting');
});

test('visual simulation survives API updates and restores the live room without dispatching', async () => {
  const storage = new Map();
  const room = await openRoom(storage);
  const dashboard = {
    agents: [{ id: 'director', status: 'idle', current_task: 'En espera' }],
    events: [],
  };
  room.consumeDashboard(dashboard);
  const agent = room.State.agents[0];
  const original = [...agent.position];
  room.startRoomSimulation();
  assert.equal(agent.routeTarget, 'work');
  assert.equal(agent.simulatedWorking, true);
  const savedBefore = storage.get(room.RoomStateKey);
  room.consumeDashboard(dashboard);
  room.saveRoomState();
  assert.equal(agent.routeTarget, 'work');
  assert.equal(storage.get(room.RoomStateKey), savedBefore);
  room.stopRoomSimulation();
  assert.equal(room.State.roomSimulation, null);
  assert.equal(agent.simulatedWorking, undefined);
  assert.deepEqual([...agent.position], original);
});

test('backend thinking, error and paused states drive distinct visual states', async () => {
  const room = await openRoom();
  const snapshot = (status) => ({
    agents: [{ id: 'scout', status, current_task: 'Investigando' }],
    events: [],
  });
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

test('terminal renders all event messages as text in chronological order', async () => {
  const room = await openRoom();
  room.State.events = [
    {
      id: 'new',
      agent: 'SCOUT',
      kind: 'status_error',
      message: '<script>unsafe</script>',
      created_at: '2026-10-23T11:00:00Z',
    },
    {
      id: 'old',
      agent: 'NEXUS',
      kind: 'mission_dispatched',
      message: 'Delegado',
      created_at: '2026-10-23T10:59:00Z',
    },
  ];
  room.renderTerminal();
  assert.equal(room.feed.children.length, 2);
  assert.match(room.feed.children[0].textContent, /NEXUS/);
  assert.match(room.feed.children[1].textContent, /<script>unsafe<\/script>/);
  assert.equal(room.feed.children[1].className, 'TerminalLine IsError');
  assert.equal(room.terminalCount.textContent, '2 REGISTROS');
});
