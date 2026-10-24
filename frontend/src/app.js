import { startCodexSessions } from './js/features/sessions.js';
import { $ } from './js/dom.js';
import { bindAccess, bindAgentCreation, bindAgentDeletion } from './js/features/access.js';
import { renderAgentUsageChart, renderCodexUsageChart } from './js/features/charts.js';
import { syncModelCatalog } from './js/features/controls.js';
import { advanceRoomRoutes, cycleWorkActions, makeSlimesWander } from './js/room/navigation.js';
import { startRoomSimulation, stopRoomSimulation } from './js/room/simulation.js';
import { restoreRoomAgent, saveRoomState } from './js/room/storage.js';
import {
  checkForDeployment,
  connectLiveStream,
  runLocalTelemetry,
  syncCodexUsage,
  syncDashboard,
  syncUsageSeries,
} from './js/services/live.js';
import { State } from './js/state.js';
import { renderDashboard, updateConnectionLabel, updateDigitalClock } from './js/ui/dashboard.js';
import { bindInteractions } from './js/ui/events.js';

startCodexSessions();
State.agents.forEach(restoreRoomAgent);
bindAgentDeletion();
$('#simulateAll').addEventListener('click', () =>
  State.roomSimulation ? stopRoomSimulation() : startRoomSimulation(),
);
bindInteractions();
bindAccess();
bindAgentCreation();
renderDashboard();
renderAgentUsageChart();
renderCodexUsageChart();
requestAnimationFrame(advanceRoomRoutes);
updateDigitalClock();
syncDashboard().catch(() => {
  updateConnectionLabel();
});
syncUsageSeries().catch(() => {});
syncModelCatalog().catch(() => {});
connectLiveStream();
syncCodexUsage().catch(() => {});
checkForDeployment().catch(() => {});
setInterval(() => syncDashboard().catch(() => {}), 2000);
setInterval(() => syncUsageSeries().catch(() => {}), 15000);
setInterval(() => syncCodexUsage().catch(() => {}), 60000);
setInterval(() => checkForDeployment().catch(() => {}), 25000);
setInterval(runLocalTelemetry, 1000);
setInterval(makeSlimesWander, 4200);
setInterval(cycleWorkActions, 3600);
setInterval(saveRoomState, 500);
setInterval(updateDigitalClock, 1000);
window.addEventListener('pagehide', saveRoomState);
document.addEventListener('visibilitychange', () => {
  if (document.hidden) saveRoomState();
  else {
    syncDashboard().catch(() => {});
    connectLiveStream();
  }
});
