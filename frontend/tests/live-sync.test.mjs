import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { SourceTextModule, SyntheticModule, createContext } from 'node:vm';

const deferred = () => {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
};
const snapshot = (name, revision = 1, epoch = 'one') => ({
  agents: [{ id: 'forge', name, status: 'standby', current_task: name }],
  events: [],
  snapshot_revision: revision,
  snapshot_epoch: epoch,
});
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

async function openLive(
  t,
  {
    fetchApi = async () => snapshot('default'),
    fetch = async () => {
      throw new Error();
    },
  } = {},
) {
  const State = {
    agents: [],
    events: [],
    operatorId: 'admin',
    monitorWorkspace: 'A',
    eventSource: null,
  };
  const noop = () => {};
  const imports = {
    '../agents/model.js': { buildVisualAgent: (agent) => ({ ...agent, work: [0, 0] }) },
    '../config.js': { API_URL: 'http://local', WorkStatuses: new Set(['thinking', 'running']) },
    '../features/charts.js': { renderAgentUsageChart: noop, renderCodexUsageChart: noop },
    '../features/metrics.js': { renderCodexUsage: noop },
    '../features/missions.js': { detectRemoteDispatches: noop },
    '../room/navigation.js': { routeToRoom: noop },
    '../state.js': { State },
    '../ui/dashboard.js': { renderDashboard: noop, updateConnectionLabel: noop },
    './api.js': { fetchApi },
  };
  const context = createContext({
    fetch,
    AbortController,
    TextDecoder,
    setTimeout,
    clearTimeout,
    Date,
  });
  const module = new SourceTextModule(
    readFileSync(new URL('../src/js/services/live.js', import.meta.url), 'utf8'),
    { context },
  );
  await module.link(
    (name) =>
      new SyntheticModule(
        Object.keys(imports[name]),
        function () {
          for (const [key, value] of Object.entries(imports[name])) this.setExport(key, value);
        },
        { context },
      ),
  );
  await module.evaluate();
  const live = module.namespace;
  t.after(() => live.resetLiveContext());
  return { live, State };
}

test('dashboard ignores older revisions and responses from retired server epochs', async (t) => {
  const { live, State } = await openLive(t);
  live.consumeDashboard(snapshot('new', 2));
  live.consumeDashboard(snapshot('old', 1));
  assert.equal(State.agents[0].name, 'new');
  State.connected = false;
  live.consumeDashboard(snapshot('new', 2));
  assert.equal(State.connected, true);
  live.consumeDashboard(snapshot('restarted', 1, 'two'));
  live.consumeDashboard(snapshot('retired', 99));
  assert.equal(State.agents[0].name, 'restarted');
});

test('late HTTP response cannot restore the previous workspace and requests do not overlap', async (t) => {
  const calls = [];
  const { live, State } = await openLive(t, {
    fetchApi: () => {
      const task = deferred();
      calls.push(task);
      return task.promise;
    },
  });
  const old = live.syncDashboard();
  const duplicate = live.syncDashboard();
  assert.equal(calls.length, 1);
  State.monitorWorkspace = 'B';
  live.resetLiveContext();
  const current = live.syncDashboard();
  calls[1].resolve(snapshot('B', 2));
  await current;
  calls[0].resolve(snapshot('A', 99));
  await Promise.all([old, duplicate]);
  assert.equal(State.agents[0].name, 'B');
});

test('stream sends explicit operator, supersedes stale polling and closes on identity change', async (t) => {
  const pending = deferred();
  let options;
  let controller;
  let polls = 0;
  const { live, State } = await openLive(t, {
    fetchApi: () => {
      polls += 1;
      return pending.promise;
    },
    fetch: async (_url, request) => {
      options = request;
      return new Response(
        new ReadableStream({
          start(stream) {
            controller = stream;
          },
        }),
      );
    },
  });
  const http = live.syncDashboard();
  live.connectLiveStream();
  await tick();
  assert.equal(options.headers['X-Operator-Id'], 'admin');
  controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(snapshot('live', 2))}\n\n`));
  await tick();
  pending.resolve(snapshot('older poll', 1));
  await http;
  assert.equal(State.agents[0].name, 'live');
  await live.syncDashboard();
  assert.equal(polls, 1, 'healthy SSE should replace polling');
  State.operatorId = 'limited';
  live.resetLiveContext();
  assert.equal(options.signal.aborted, true);
  assert.equal(State.streamHealthy, false);
});
