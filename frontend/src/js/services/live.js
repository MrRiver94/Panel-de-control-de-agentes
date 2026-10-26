import { buildVisualAgent } from '../agents/model.js';
import { API_URL, WorkStatuses } from '../config.js';
import { renderAgentUsageChart, renderCodexUsageChart } from '../features/charts.js';
import { renderCodexUsage } from '../features/metrics.js';
import { detectRemoteDispatches } from '../features/missions.js';
import { routeToRoom } from '../room/navigation.js';
import { State } from '../state.js';
import { renderDashboard, updateConnectionLabel } from '../ui/dashboard.js';
import { fetchApi } from './api.js';

let generation = 0;
let activeContext;
let pendingDashboard;
let reconnectTimer;
let lastRevision = -1;
let lastEpoch;
const retiredEpochs = new Set();
const contextKey = () => JSON.stringify([State.operatorId, State.monitorWorkspace || '']);

function resetLiveContext() {
  generation += 1;
  activeContext = contextKey();
  clearTimeout(reconnectTimer);
  State.eventSource?.close();
  State.eventSource = null;
  State.streamHealthy = false;
  pendingDashboard?.controller.abort();
  pendingDashboard = null;
  lastRevision = -1;
  lastEpoch = undefined;
  retiredEpochs.clear();
  State.connected = false;
  updateConnectionLabel();
}

function currentGeneration() {
  if (activeContext !== contextKey()) resetLiveContext();
  return generation;
}

function consumeDashboard(dashboard, { replay = false } = {}) {
  if (!Array.isArray(dashboard?.agents)) throw new Error('Dashboard inválido.');
  const epoch = dashboard.snapshot_epoch;
  const revision = dashboard.snapshot_revision;
  if (epoch && retiredEpochs.has(epoch)) return;
  State.connected = true;
  State.lastTelemetryAt = new Date();
  updateConnectionLabel();
  if (epoch && Number.isInteger(revision)) {
    if (lastEpoch !== epoch) {
      if (lastEpoch) retiredEpochs.add(lastEpoch);
      lastEpoch = epoch;
      lastRevision = -1;
    }
    if (!replay && revision <= lastRevision) return;
    lastRevision = Math.max(lastRevision, revision);
  }
  State.latestDashboard = dashboard;
  State.externalSessions = dashboard.external_sessions || [];
  dashboard.agents.forEach((remoteAgent) => {
    let localAgent = State.agents.find((agent) => agent.id === remoteAgent.id);
    const isNew = !localAgent;
    if (isNew) {
      localAgent = buildVisualAgent(remoteAgent);
      State.agents.push(localAgent);
    }
    const status = WorkStatuses.has(remoteAgent.status) ? 'working' : 'sleeping';
    if (
      !State.roomSimulation &&
      !localAgent.roomStateRestored &&
      !localAgent.route &&
      status === 'working' &&
      (State.dashboardReady === false || isNew)
    ) {
      localAgent.position = [...localAgent.work];
      localAgent.roomZone = 'work';
      localAgent.visualPhase = 'working';
    }
    Object.assign(localAgent, remoteAgent, {
      status,
      operationalStatus: remoteAgent.status,
      workAction: remoteAgent.work_action || undefined,
      hue: remoteAgent.display_hue || localAgent.hue,
      action:
        remoteAgent.current_task === 'En espera'
          ? remoteAgent.default_action || localAgent.action
          : remoteAgent.current_task,
    });
    if (!State.roomSimulation) routeToRoom(localAgent, status === 'working' ? 'work' : 'rest');
  });
  const remoteIds = new Set(dashboard.agents.map((agent) => agent.id));
  State.agents = State.agents.filter((agent) => remoteIds.has(agent.id));
  if (!State.agents.some((agent) => agent.id === State.selectedAgentId))
    State.selectedAgentId = State.agents[0]?.id;
  detectRemoteDispatches(dashboard.events || []);
  State.events = dashboard.events || [];
  renderDashboard();
}

async function syncDashboard() {
  const version = currentGeneration();
  if (State.streamHealthy) return;
  if (pendingDashboard) return pendingDashboard.promise;
  const context = contextKey();
  const controller = new AbortController();
  const query = State.monitorWorkspace
    ? `?workspace=${encodeURIComponent(State.monitorWorkspace)}`
    : '';
  const task = { controller };
  pendingDashboard = task;
  task.promise = (async () => {
    try {
      const dashboard = await fetchApi('/api/dashboard' + query, { signal: controller.signal });
      if (version === generation && context === contextKey()) consumeDashboard(dashboard);
    } catch (error) {
      if (version === generation && context === contextKey() && !controller.signal.aborted) {
        State.connected = false;
        updateConnectionLabel();
        throw error;
      }
    } finally {
      if (pendingDashboard === task) pendingDashboard = null;
    }
  })();
  return task.promise;
}

function connectLiveStream() {
  const version = currentGeneration();
  if (State.eventSource) return;
  const context = contextKey();
  const query = State.monitorWorkspace
    ? `?workspace=${encodeURIComponent(State.monitorWorkspace)}`
    : '';
  const controller = new AbortController();
  let reader;
  let watchdog;
  const stream = {
    close() {
      clearTimeout(watchdog);
      controller.abort();
      void reader?.cancel().catch(() => {});
    },
  };
  State.eventSource = stream;
  const alive = () =>
    version === generation && context === contextKey() && State.eventSource === stream;
  const refreshWatchdog = () => {
    clearTimeout(watchdog);
    watchdog = setTimeout(() => controller.abort(), 15000);
  };
  void (async () => {
    try {
      refreshWatchdog();
      const response = await fetch(`${API_URL}/api/stream${query}`, {
        headers: { Accept: 'text/event-stream', 'X-Operator-Id': State.operatorId },
        signal: controller.signal,
        cache: 'no-store',
      });
      if (!response.ok || !response.body) throw new Error(`Stream ${response.status}`);
      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (alive()) {
        const { done, value } = await reader.read();
        if (done) break;
        if (!alive()) break;
        refreshWatchdog();
        State.streamHealthy = true;
        State.connected = true;
        State.lastTelemetryAt = new Date();
        updateConnectionLabel();
        buffer = (buffer + decoder.decode(value, { stream: true })).replaceAll('\r\n', '\n');
        if (buffer.length > 1_000_000) throw new Error('Stream demasiado grande.');
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) >= 0) {
          const block = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const data = block
            .split('\n')
            .filter((line) => line.startsWith('data:'))
            .map((line) => line.slice(5).trimStart())
            .join('\n');
          if (data) consumeDashboard(JSON.parse(data));
        }
      }
    } catch {
      // Polling remains available until a connection with this context recovers.
    } finally {
      stream.close();
      if (alive()) {
        State.streamHealthy = false;
        State.connected = false;
        State.eventSource = null;
        updateConnectionLabel();
        reconnectTimer = setTimeout(() => {
          if (version === generation && context === contextKey()) connectLiveStream();
        }, 2500);
      }
    }
  })();
}

async function checkForDeployment() {
  const response = await fetch(`app-version.json?check=${Date.now()}`, { cache: 'no-store' });
  if (!response.ok) return;
  const { buildId } = await response.json();
  if (State.buildId && State.buildId !== buildId) {
    window.location.reload();
    return;
  }
  State.buildId = buildId;
}

async function syncCodexUsage() {
  const context = contextKey();
  const usage = await fetchApi('/api/codex-usage');
  if (context !== contextKey()) return;
  State.codexUsage = usage;
  renderCodexUsage();
  renderCodexUsageChart();
}

async function syncUsageSeries() {
  const context = contextKey();
  const series = await fetchApi('/api/usage-series?minutes=60');
  if (context !== contextKey()) return;
  State.agentUsageSeries = series;
  renderAgentUsageChart();
}

export {
  consumeDashboard,
  syncDashboard,
  connectLiveStream,
  resetLiveContext,
  checkForDeployment,
  syncCodexUsage,
  syncUsageSeries,
};
