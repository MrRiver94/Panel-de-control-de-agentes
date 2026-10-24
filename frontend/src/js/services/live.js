import { buildVisualAgent } from '../agents/model.js';
import { API_URL, WorkStatuses } from '../config.js';
import { renderAgentUsageChart, renderCodexUsageChart } from '../features/charts.js';
import { renderCodexUsage, renderMetricsPanel } from '../features/metrics.js';
import { detectRemoteDispatches } from '../features/missions.js';
import { routeToRoom } from '../room/navigation.js';
import { State } from '../state.js';
import { renderDashboard, updateConnectionLabel } from '../ui/dashboard.js';
import { fetchApi } from './api.js';

function consumeDashboard(dashboard) {
  State.latestDashboard = dashboard;
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
  State.connected = true;
  State.lastTelemetryAt = new Date();
  updateConnectionLabel();
  renderDashboard();
}

async function syncDashboard() {
  consumeDashboard(await fetchApi('/api/dashboard'));
}

function connectLiveStream() {
  if (State.eventSource) return;
  const stream = new EventSource(`${API_URL}/api/stream`);
  State.eventSource = stream;
  stream.onmessage = (event) => {
    try {
      consumeDashboard(JSON.parse(event.data));
    } catch {}
  };
  stream.onerror = () => {
    stream.close();
    if (State.eventSource === stream) {
      State.eventSource = null;
      setTimeout(connectLiveStream, 2500);
    }
  };
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
  const usage = await fetchApi('/api/codex-usage');
  State.codexUsage = usage;
  renderCodexUsage();
  renderCodexUsageChart();
}

async function syncUsageSeries() {
  State.agentUsageSeries = await fetchApi('/api/usage-series?minutes=60');
  renderAgentUsageChart();
}

function runLocalTelemetry() {
  if (State.connected) return;
  let changed = false;
  State.agents.forEach((agent) => {
    if (agent.status !== 'working') return;
    const rates = { low: 2, medium: 4, high: 7, xhigh: 11 };
    agent.tokens_used = Math.min(
      agent.token_budget,
      agent.tokens_used + rates[agent.reasoning_effort],
    );
    if (agent.tokens_used >= agent.token_budget) agent.status = 'sleeping';
    changed = true;
  });
  if (changed) {
    State.lastTelemetryAt = new Date();
    renderMetricsPanel();
  }
}

export {
  consumeDashboard,
  syncDashboard,
  connectLiveStream,
  checkForDeployment,
  syncCodexUsage,
  syncUsageSeries,
  runLocalTelemetry,
};
