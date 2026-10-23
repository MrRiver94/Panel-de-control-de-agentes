const API_URL = 'http://127.0.0.1:8000';
const EffortLevels = ['low', 'medium', 'high', 'xhigh'];
const DemoAgents = [
  {id:'director',name:'DIRECTOR',role:'Dirección',tone:'#ffd166',hue:'-100deg',tokens_used:1260,token_budget:6000,reasoning_effort:'high',status:'sleeping',idle_mode:'Coffee',sleep:[36,44],work:[80,25],action:'priorizando'},
  {id:'nexus',name:'NEXUS',role:'Coordinación',tone:'#d9f45a',hue:'68deg',tokens_used:2870,token_budget:8000,reasoning_effort:'high',status:'sleeping',idle_mode:'Eating',sleep:[54,48],work:[51,17],action:'planificando'},
  {id:'scout',name:'SCOUT',role:'Investigación',tone:'#79e8ee',hue:'0deg',tokens_used:1920,token_budget:5500,reasoning_effort:'medium',status:'sleeping',idle_mode:'Sleep',sleep:[44,71],work:[18,28],action:'investigando'},
  {id:'forge',name:'FORGE',role:'Construcción',tone:'#ff789d',hue:'135deg',tokens_used:840,token_budget:7000,reasoning_effort:'medium',status:'sleeping',idle_mode:'Sleep',sleep:[58,71],work:[20,64],action:'construyendo'},
  {id:'sentinel',name:'SENTINEL',role:'Calidad',tone:'#ab8cff',hue:'230deg',tokens_used:610,token_budget:4500,reasoning_effort:'low',status:'sleeping',idle_mode:'Coffee',sleep:[39,34],work:[79,63],action:'revisando'},
  {id:'muse',name:'MUSE',role:'Dirección de arte',tone:'#ffaf5f',hue:'-45deg',tokens_used:430,token_budget:6200,reasoning_effort:'high',status:'sleeping',idle_mode:'Eating',sleep:[55,34],work:[49,33],action:'diseñando'}
];
const LoungeRoutes = {
  director: [[36,44], [38,53], [44,57], [32,49]],
  nexus: [[54,48], [61,53], [56,57], [63,44]],
  sentinel: [[39,34], [45,37], [43,29], [33,38]],
  muse: [[55,34], [61,38], [64,31], [52,29]]
};
const BreakActivities = { director: 'phone', nexus: 'coffee', scout: 'gameboy', forge: 'talk', sentinel: 'coffee', muse: 'talk' };
const FallbackModelCatalog = { providers: [
  {id:'codex', label:'Codex / OpenAI', models:['gpt-6.1-sol','gpt-6-astra','gpt-6-luna']},
  {id:'anthropic', label:'Anthropic / Claude', models:['claude-sonnet-4-6','claude-opus-4-6','claude-haiku-4-5-20251001']}
], source:'suggested' };
// Ground-level coordinates on the uncluttered v5 floor plan.
const RoomStations = {
  director: {rest:[41,51], desk:[78,36], door:[[64,40],[67,36]]},
  nexus: {rest:[49,51], desk:[48,23], door:[[49,38],[49,31]]},
  scout: {rest:[43,62], desk:[21,37], door:[[37,43],[33,36]]},
  forge: {rest:[55,62], desk:[20,70], door:[[41,54],[34,61],[31,65]]},
  sentinel: {rest:[57,51], desk:[79,70], door:[[59,54],[65,61],[68,65]]},
  muse: {rest:[49,61], desk:[79,37], door:[[61,43],[66,36]]}
};
const SharedRestStops = [[42,52],[47,48],[52,48],[57,52],[53,58],[47,59]];
DemoAgents.forEach((agent) => { agent.sleep = [...RoomStations[agent.id].rest]; agent.work = [...RoomStations[agent.id].desk]; agent.position = [...agent.sleep]; agent.roomZone = 'rest'; agent.provider = 'codex'; agent.model = ''; });
Object.assign(LoungeRoutes, {
  director:[[41,51],[43,47],[46,51]], nexus:[[49,51],[50,46],[53,51]],
  scout:[[43,62],[41,57],[44,54]], forge:[[55,62],[58,57],[55,54]],
  sentinel:[[57,51],[55,47],[53,51]], muse:[[49,61],[47,56],[51,55]]
});
const State = { agents: structuredClone(DemoAgents), events: [], auditEvents: [], access: null, operatorId: localStorage.getItem('slimeops-operator') || 'super-admin', selectedAgentId: 'nexus', profileAgentId: 'nexus', connected: false, lastTelemetryAt: null, codexUsage: null, agentUsageSeries: null, modelCatalog: FallbackModelCatalog, controlDrafts: new Map(), dashboardReady: false, knownDispatches: new Set(), eventSource: null, buildId: null, openAgentId: null, roomZoom: 1, roomPan: 0, roomPanY: 0, roomSimulation: null, latestDashboard: null };
const RoomStateKey = 'slimeops-room-v6';
const validPoint = (point) => Array.isArray(point) && point.length === 2 && point.every((value) => Number.isFinite(value) && value >= 0 && value <= 100);
function readRoomState() {
  try {
    const saved = JSON.parse(localStorage.getItem(RoomStateKey));
    return saved?.savedAt > Date.now() - 86400000 && saved?.savedAt <= Date.now() && saved.agents && typeof saved.agents === 'object' ? saved.agents : {};
  } catch { return {}; }
}
const SavedRoomAgents = readRoomState();
function restoreRoomAgent(agent) {
  const saved = SavedRoomAgents[agent.id];
  if (!saved || !validPoint(saved.position) || !['rest', 'work'].includes(saved.roomZone)) return agent;
  agent.position = [...saved.position];
  agent.roomZone = saved.roomZone;
  agent.status = saved.status === 'working' ? 'working' : 'sleeping';
  agent.visualPhase = saved.visualPhase === 'commuting' ? 'commuting' : agent.roomZone === 'work' ? 'working' : undefined;
  agent.loungeStep = Number.isInteger(saved.loungeStep) ? saved.loungeStep : undefined;
  if (validPoint(saved.sleep)) agent.sleep = [...saved.sleep];
  if (Array.isArray(saved.route) && saved.route.length >= 2 && saved.route.length <= 12 && saved.route.every(validPoint) && Number.isInteger(saved.routeIndex) && saved.routeIndex >= 0 && saved.routeIndex < saved.route.length - 1 && Number.isFinite(saved.segmentStart) && saved.segmentStart <= Date.now() && ['rest', 'work'].includes(saved.routeTarget)) {
    agent.route = saved.route.map((point) => [...point]);
    agent.routeIndex = saved.routeIndex;
    agent.segmentStart = saved.segmentStart;
    agent.routeTarget = saved.routeTarget;
    agent.nextRoomZone = ['rest', 'work'].includes(saved.nextRoomZone) ? saved.nextRoomZone : undefined;
    agent.visualPhase = saved.visualPhase === 'commuting' ? 'commuting' : undefined;
    agent.moving = true;
  }
  agent.roomStateRestored = true;
  return agent;
}
State.agents.forEach(restoreRoomAgent);
function saveRoomState() {
  if (State.roomSimulation) return;
  try {
    const agents = Object.fromEntries(State.agents.map((agent) => [agent.id, {
      position: agent.position, sleep: agent.sleep, roomZone: agent.roomZone, status: agent.status,
      visualPhase: agent.visualPhase, loungeStep: agent.loungeStep, route: agent.route,
      routeIndex: agent.routeIndex, segmentStart: agent.segmentStart, routeTarget: agent.routeTarget,
      nextRoomZone: agent.nextRoomZone
    }]));
    localStorage.setItem(RoomStateKey, JSON.stringify({savedAt:Date.now(), agents}));
  } catch { /* Storage can be unavailable in private browsing. */ }
}
const $ = (selector) => document.querySelector(selector);
const formatNumber = (value) => new Intl.NumberFormat('es-ES').format(value);
const uppercase = (value) => value.toUpperCase();
const getSelectedAgent = () => State.agents.find((agent) => agent.id === State.selectedAgentId);
document.addEventListener('click', async (event) => { const button = event.target.closest('[data-agent-delete]'); if (!button || !confirm(`Eliminar ${button.dataset.agentDelete}?`)) return; try { await fetchApi(`/api/agents/${button.dataset.agentDelete}`, {method:'DELETE'}); State.agents = State.agents.filter((agent) => agent.id !== button.dataset.agentDelete); State.selectedAgentId = State.agents[0]?.id; refreshAccessActions(); renderDashboard(); } catch (error) { alert(`No se pudo eliminar: ${error.message}`); } });
const fetchApi = async (path, options = {}) => { const response = await fetch(API_URL + path, {...options, headers:{'Content-Type':'application/json','X-Operator-Id':State.operatorId,...(options.headers || {})}}); if (!response.ok) throw new Error(await response.text()); return response.json(); };
function applyAccess() { const role = State.access?.roles.find((item) => item.id === State.access?.users.find((item) => item.id === State.operatorId)?.role_id); const permissions = role?.permissions || []; const allowed = (permission) => permissions.includes('*') || permissions.includes(permission); $('#saveControls').disabled = !allowed('agents.update'); $('#openCustomizer').disabled = !allowed('agents.update'); $('#missionForm button').disabled = !allowed('mission.create'); $('#openAccess').style.display = allowed('access.manage') ? '' : 'none'; }
function renderAccess() { const tree = State.access; if (!tree) return; $('#activeUserSelect').innerHTML = tree.users.map((user) => `<option value="${user.id}">${user.name}</option>`).join(''); $('#activeUserSelect').value = State.operatorId; $('#newUserRole').innerHTML = tree.roles.map((role) => `<option value="${role.id}">${role.name}</option>`).join(''); $('#accessTree').innerHTML = tree.roles.map((role) => `<section><b>${role.name}</b><small>${role.permissions.join(' · ')}</small>${tree.users.filter((user) => user.role_id === role.id).map((user) => `<p>└ ${user.name}</p>`).join('') || '<p>└ sin usuarios</p>'}</section>`).join(''); applyAccess(); }
async function openAccess() { try { State.access = await fetchApi('/api/access/tree'); renderAccess(); renderAccessActions(); $('#accessDialog').showModal(); } catch { alert('No tienes permiso para gestionar accesos.'); } }
function renderAccessActions() { const tree = State.access; if (!tree || $('#accessActions')) return; const roleCards = tree.roles.map((role) => `<div class="AccessRow"><span>ROL: ${role.name}</span>${role.id === 'super-admin' ? '<small>PROTEGIDO</small>' : `<button data-role-edit="${role.id}">EDITAR</button><button data-role-delete="${role.id}">BORRAR</button>`}</div>`).join(''); const userCards = tree.users.map((user) => `<div class="AccessRow"><span>USUARIO: ${user.name}</span>${user.id === 'super-admin' ? '<small>PROTEGIDO</small>' : `<button data-user-edit="${user.id}">EDITAR</button><button data-user-delete="${user.id}">BORRAR</button>`}</div>`).join(''); const selected = getSelectedAgent(); const agentAction = selected && !DemoAgents.some((agent) => agent.id === selected.id) ? `<button class="SecondaryButton" data-agent-delete="${selected.id}">ELIMINAR ${selected.name}</button>` : ''; $('#accessTree').insertAdjacentHTML('afterend', `<section class="AccessActions" id="accessActions"><button class="PrimaryButton" id="openCreateAgent" type="button">+ CREAR AGENTE</button>${agentAction}<h3>GESTIÓN CRUD</h3>${roleCards}${userCards}</section>`); }
function refreshAccessActions() { $('#accessActions')?.remove(); renderAccessActions(); }
function buildVisualAgent(remote) { const stations = Object.values(RoomStations); const station = RoomStations[remote.id] || stations[State.agents.length % stations.length]; return restoreRoomAgent({...remote, hue:remote.display_hue || '0deg', sleep:[...station.rest], work:[...station.desk], position:[...station.rest], roomZone:'rest', action:remote.default_action || 'en espera', visualPhase:undefined}); }
function selectedCreateActions() { return [...document.querySelectorAll('#createAgentActions input:checked')].map((input) => input.value); }
function bindAgentCreation() { $('#accessDialog').addEventListener('click', async (event) => { const button = event.target.closest('button'); if (!button) return; if (button.id === 'openCreateAgent') { $('#createAgentDialog').showModal(); return; } try { if (button.dataset.roleEdit) { const role = State.access.roles.find((item) => item.id === button.dataset.roleEdit); const name = prompt('Nombre del rol', role.name); if (!name) return; const permissions = prompt('Permisos separados por coma', role.permissions.join(',')); if (!permissions) return; State.access = await fetchApi(`/api/access/roles/${role.id}`, {method:'POST', body:JSON.stringify({name, permissions:permissions.split(',').map((item) => item.trim()).filter(Boolean)})}); renderAccess(); refreshAccessActions(); } if (button.dataset.roleDelete && confirm('¿Eliminar este rol?')) { State.access = await fetchApi(`/api/access/roles/${button.dataset.roleDelete}`, {method:'DELETE'}); renderAccess(); refreshAccessActions(); } if (button.dataset.userEdit) { const user = State.access.users.find((item) => item.id === button.dataset.userEdit); const name = prompt('Nombre del usuario', user.name); if (!name) return; const role_id = prompt(`Rol (${State.access.roles.map((role) => role.id).join(', ')})`, user.role_id); if (!role_id) return; State.access = await fetchApi(`/api/access/users/${user.id}`, {method:'POST', body:JSON.stringify({name, role_id})}); renderAccess(); refreshAccessActions(); } if (button.dataset.userDelete && confirm('¿Eliminar este usuario?')) { State.access = await fetchApi(`/api/access/users/${button.dataset.userDelete}`, {method:'DELETE'}); renderAccess(); refreshAccessActions(); } } catch (error) { alert(`No se pudo guardar: ${error.message}`); } }); $('#closeCreateAgent').addEventListener('click', () => $('#createAgentDialog').close()); $('#createAgentForm').addEventListener('submit', async (event) => { event.preventDefault(); const enabled_actions = selectedCreateActions(); if (!enabled_actions.length) return; const payload = {name:$('#createAgentName').value.trim(), role:$('#createAgentRole').value.trim(), tone:$('#createAgentTone').value, display_hue:'0deg', idle_mode:$('#createAgentIdle').value, default_action:$('#createAgentAction').value.trim(), enabled_actions, token_budget:Number($('#createAgentBudget').value), reasoning_effort:$('#createAgentEffort').value}; try { const created = await fetchApi('/api/agents', {method:'POST', body:JSON.stringify(payload)}); State.agents.push(buildVisualAgent(created)); State.selectedAgentId = created.id; renderDashboard(); $('#createAgentDialog').close(); } catch (error) { alert(`No se pudo crear el agente: ${error.message}`); } }); }

function getControlDraft(agent) { const current = State.controlDrafts.get(agent.id); if (current?.dirty) return current; const fresh = {token_budget:agent.token_budget, reasoning_effort:agent.reasoning_effort, provider:agent.provider || 'codex', model:agent.model || '', dirty:false}; State.controlDrafts.set(agent.id, fresh); return fresh; }
function modelsFor(provider) { return State.modelCatalog.providers.find((item) => item.id === provider)?.models || []; }
function renderControlPanel() { const agent = getSelectedAgent(); const draft = getControlDraft(agent); $('#agentSelect').innerHTML = State.agents.map((item) => `<option value="${item.id}">${item.name} — ${item.role}</option>`).join(''); $('#agentSelect').value = agent.id; $('#budgetInput').value = draft.token_budget; const providers = $('#providerSelect'); providers.replaceChildren(...State.modelCatalog.providers.map((item) => new Option(item.label, item.id))); providers.value = draft.provider; const modelSelect = $('#modelSelect'); const models = [...modelsFor(draft.provider)]; if (draft.model && !models.includes(draft.model)) models.unshift(draft.model); modelSelect.replaceChildren(new Option('Sin asignar', ''), ...models.map((model) => new Option(model, model))); modelSelect.value = draft.model; $('#modelHint').textContent = State.modelCatalog.source === 'configured' ? 'Modelos recibidos de la configuración de la API.' : 'Modelos sugeridos; la disponibilidad depende de tus cuentas. El panel aún no ejecuta inferencias.'; $('#effortSelector').innerHTML = EffortLevels.map((level) => `<button class="EffortButton ${draft.reasoning_effort === level ? 'Active' : ''}" data-effort="${level}">${uppercase(level)}</button>`).join(''); }
async function syncModelCatalog() { try { const catalog = await fetchApi('/api/models'); if (Array.isArray(catalog.providers) && catalog.providers.length) State.modelCatalog = catalog; } catch { State.modelCatalog = FallbackModelCatalog; } renderControlPanel(); }
function getProfileAgent() { return State.agents.find((agent) => agent.id === State.profileAgentId) || getSelectedAgent(); }
function renderCustomizer() { const agent = getProfileAgent(); $('#profileAgentSelect').innerHTML = State.agents.map((item) => `<option value="${item.id}">${item.name} — ${item.role}</option>`).join(''); $('#profileAgentSelect').value = agent.id; $('#profileName').value = agent.name; $('#profileRole').value = agent.role; $('#profileAction').value = agent.default_action || agent.action; $('#profileTone').value = agent.tone; $('#profileHue').value = agent.display_hue || agent.hue || '0deg'; $('#profileIdle').value = agent.idle_mode || 'Coffee'; document.querySelectorAll('#profileActions input').forEach((input) => { input.checked = (agent.enabled_actions || []).includes(input.value); }); $('#previewName').textContent = agent.name; $('#previewRole').textContent = agent.role; $('#previewActions').textContent = (agent.enabled_actions || []).join(' · ').toUpperCase(); $('#previewSlime').style.setProperty('--preview-tone', agent.tone); $('#previewSlime').style.setProperty('--preview-hue', agent.display_hue || agent.hue || '0deg'); }
function openCustomizer() { State.profileAgentId = State.selectedAgentId; renderCustomizer(); $('#customizerDialog').showModal(); }
function previewCustomizer() { const agent = getProfileAgent(); const selectedActions = [...document.querySelectorAll('#profileActions input:checked')].map((input) => input.value); $('#previewName').textContent = $('#profileName').value || agent.name; $('#previewRole').textContent = $('#profileRole').value || agent.role; $('#previewActions').textContent = selectedActions.join(' · ').toUpperCase() || 'SIN ACCIONES'; $('#previewSlime').style.setProperty('--preview-tone', $('#profileTone').value); $('#previewSlime').style.setProperty('--preview-hue', $('#profileHue').value); }
async function saveCustomizer(event) { event.preventDefault(); const agent = getProfileAgent(); const enabled_actions = [...document.querySelectorAll('#profileActions input:checked')].map((input) => input.value); if (!enabled_actions.length) { $('#customizerHint').textContent = 'Selecciona al menos una acción.'; return; } const profile = {name: $('#profileName').value.trim(), role: $('#profileRole').value.trim(), default_action: $('#profileAction').value.trim(), tone: $('#profileTone').value, display_hue: $('#profileHue').value, idle_mode: $('#profileIdle').value, enabled_actions}; if (!profile.name || !profile.role || !profile.default_action) return; Object.assign(agent, profile, {hue: profile.display_hue, action: profile.default_action}); try { const updated = await fetchApi(`/api/agents/${agent.id}/profile`, {method:'POST', body:JSON.stringify(profile)}); Object.assign(agent, updated, {hue: updated.display_hue, action: updated.default_action}); $('#customizerHint').textContent = 'Perfil guardado y auditado.'; renderDashboard(); setTimeout(() => $('#customizerDialog').close(), 450); } catch { $('#customizerHint').textContent = 'Guardado local: conecta la API para persistirlo.'; renderDashboard(); } }
function renderMetricsPanel() { const used = State.agents.reduce((sum, agent) => sum + agent.tokens_used, 0); const budget = State.agents.reduce((sum, agent) => sum + agent.token_budget, 0); const active = State.agents.filter((agent) => agent.status === 'working').length; const usage = Math.min(100, Math.round((used / budget) * 100)); const margin = 100 - usage; const health = usage < 65 ? 'EFICIENTE' : usage < 85 ? 'VIGILAR' : 'REVISAR'; $('#budgetUsage').textContent = `${usage}%`; $('#budgetMargin').textContent = `${margin}%`; $('#activeAgents').textContent = `${active}/${State.agents.length}`; $('#budgetHealth').textContent = health; $('#budgetBar').style.width = `${usage}%`; $('#budgetNumbers').textContent = `${formatNumber(used)} / ${formatNumber(budget)} tokens`; $('#efficiencyMessage').textContent = usage < 65 ? 'Gasto bajo control' : usage < 85 ? 'Prioriza tareas complejas' : 'Ajusta límites'; $('#telemetryStamp').textContent = State.lastTelemetryAt ? `Actualizado ${State.lastTelemetryAt.toLocaleTimeString('es-ES', {hour:'2-digit', minute:'2-digit', second:'2-digit'})} · ${State.connected ? 'API en directo' : 'modo simulación'}` : 'Esperando telemetría'; }
function formatReset(unixSeconds) { if (!unixSeconds) return 'Sin dato de reinicio'; const date = new Date(unixSeconds * 1000); return `Reinicia ${date.toLocaleDateString('es-ES', {day:'2-digit', month:'short'})} · ${date.toLocaleTimeString('es-ES', {hour:'2-digit', minute:'2-digit'})}`; }
function renderCodexUsage() { const usage = State.codexUsage; if (!usage) return; if (!usage.available) { $('#codexUsageStatus').textContent = 'Uso local no disponible: abre Codex en este equipo.'; return; } const latestDay = usage.daily_buckets?.at(-1); $('#fiveHourRemaining').textContent = `${usage.five_hour.remaining_percent}%`; $('#weeklyRemaining').textContent = `${usage.weekly.remaining_percent}%`; $('#fiveHourReset').textContent = formatReset(usage.five_hour.resets_at); $('#weeklyReset').textContent = formatReset(usage.weekly.resets_at); $('#codexPlan').textContent = `Plan ${(usage.plan || '—').toUpperCase()}`; $('#resetCredits').textContent = `${usage.reset_credits} recargas`; $('#dailyTokens').textContent = latestDay ? `${formatNumber(latestDay.tokens)} tokens · último día` : 'Actividad sin datos'; $('#codexUsageStatus').textContent = `Datos reales de Codex · ${new Date(usage.refreshed_at).toLocaleTimeString('es-ES', {hour:'2-digit', minute:'2-digit', second:'2-digit'})}`; }
const compactTokens = (value) => new Intl.NumberFormat('es-ES', {notation:'compact', maximumFractionDigits:1}).format(value);
const chartGrid = '<path class="ChartGrid" d="M10 24H350 M10 67H350 M10 110H350" />';
function emptyUsageChart(id, message) { const box = $(id); box.innerHTML = `<div class="UsageChartEmpty">${message}</div>`; box.setAttribute('aria-label', message); }
function renderAgentUsageChart() {
  const points = (State.agentUsageSeries?.points || []).map((point) => ({time:Date.parse(point.at), rate:Number(point.tokens_per_minute)})).filter((point) => Number.isFinite(point.time) && Number.isFinite(point.rate));
  if (points.length < 2) { emptyUsageChart('#agentUsageChart', 'Esperando dos muestras del medidor'); $('#agentPeak').textContent = 'PICO —'; $('#agentUsageNote').textContent = 'El historial comienza ahora; no se inventan datos anteriores.'; return; }
  const end = Date.now(); const start = end - 60 * 60 * 1000; const peakRate = Math.max(...points.map((point) => point.rate)); const maximum = Math.max(1, peakRate);
  const coords = points.map((point) => [Math.max(10, Math.min(350, 10 + (point.time - start) / (end - start) * 340)), 110 - point.rate / maximum * 82]);
  const path = coords.map(([x,y], index) => `${index ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const [peakX, peakY] = coords[points.findIndex((point) => point.rate === peakRate)];
  const [lastX, lastY] = coords.at(-1);
  $('#agentUsageChart').innerHTML = `<svg viewBox="0 0 360 132" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="agentChartFill" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#7ee2e8" stop-opacity=".28"/><stop offset="1" stop-color="#7ee2e8" stop-opacity="0"/></linearGradient></defs>${chartGrid}<path d="${path} L${lastX.toFixed(1)} 110 L${coords[0][0].toFixed(1)} 110 Z" fill="url(#agentChartFill)"/><path class="ChartLine" d="${path}"/><circle class="ChartPoint ChartPeak" cx="${peakX.toFixed(1)}" cy="${peakY.toFixed(1)}" r="5"/><circle class="ChartPoint" cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="4"/></svg>`;
  $('#agentUsageChart').setAttribute('aria-label', `Ritmo de uso de agentes durante la última hora. Pico ${formatNumber(peakRate)} tokens por minuto.`);
  $('#agentPeak').textContent = `PICO ${compactTokens(peakRate)}`;
  $('#agentUsageNote').textContent = `${points.length} muestras guardadas · ritmo del medidor local`;
}
function renderCodexUsageChart() {
  const buckets = State.codexUsage?.available ? State.codexUsage.daily_buckets || [] : [];
  const byDay = new Map(buckets.filter((row) => /^\d{4}-\d{2}-\d{2}$/.test(row.startDate) && Number.isFinite(Number(row.tokens))).map((row) => [row.startDate, Math.max(0, Number(row.tokens))]));
  if (!byDay.size) { emptyUsageChart('#codexUsageChart', 'Sin historial diario de Codex disponible'); $('#codexPeak').textContent = 'PICO —'; $('#codexUsageNote').textContent = 'Conecta la API local para consultar el uso diario.'; return; }
  const today = new Date(); const days = Array.from({length:7}, (_, index) => new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate() - 6 + index)).toISOString().slice(0,10));
  const values = days.map((day) => byDay.get(day) || 0); const maximum = Math.max(...values);
  if (!maximum) { emptyUsageChart('#codexUsageChart', 'Aún no hay tokens en los últimos 7 días'); $('#codexPeak').textContent = 'PICO —'; return; }
  const peakIndex = values.indexOf(maximum);
  const bars = values.map((value, index) => { const height = value ? Math.max(3, value / maximum * 82) : 0; const x = 19 + index * 46; return `<rect class="${index === peakIndex ? 'ChartBarPeak' : 'ChartBar'}" x="${x}" y="${(110 - height).toFixed(1)}" width="28" height="${height.toFixed(1)}" rx="1"><title>${days[index]} · ${formatNumber(value)} tokens</title></rect><text x="${x + 14}" y="125" text-anchor="middle">${Number(days[index].slice(-2))}</text>`; }).join('');
  $('#codexUsageChart').innerHTML = `<svg viewBox="0 0 360 132" preserveAspectRatio="none" aria-hidden="true">${chartGrid}${bars}</svg>`;
  $('#codexUsageChart').setAttribute('aria-label', `Tokens diarios de Codex en los últimos siete días. Pico ${formatNumber(maximum)} tokens el ${days[peakIndex]}.`);
  $('#codexPeak').textContent = `PICO ${compactTokens(maximum)}`;
  $('#codexUsageNote').textContent = `Máximo ${days[peakIndex]} · ${formatNumber(maximum)} tokens`;
}
function eventLabel(event) { return event.kind.replaceAll('_', ' ').toUpperCase(); }
function renderActivityLog() { $('#activityLog').innerHTML = State.events.map((event) => `<article class="ActivityItem"><time>${new Date(event.created_at).toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'})}</time><div><b>${event.agent} · ${eventLabel(event)}</b><br><span>${event.message}</span></div></article>`).join('') || '<div class="ActivityItem"><time>—</time><span>Sin actividad aún.</span></div>'; }
function renderAuditHistory() { const events = State.auditEvents.length ? State.auditEvents : State.events; $('#auditCount').textContent = `${events.length} EVENTOS GUARDADOS`; $('#auditHistory').innerHTML = events.map((event) => `<article class="AuditRecord"><time>${new Date(event.created_at).toLocaleString('es-ES',{dateStyle:'short',timeStyle:'medium'})}</time><div><b>${event.agent}</b><em>${eventLabel(event)}</em><p>${event.message}</p><small>ENTRADA ${formatNumber(event.input_tokens)} · SALIDA ${formatNumber(event.output_tokens)} · RAZONAMIENTO ${formatNumber(event.reasoning_tokens)} · TOTAL ${formatNumber(event.tokens)}</small></div></article>`).join('') || '<p class="AuditEmpty">Aún no hay actividad guardada.</p>'; }
async function openAuditHistory() { try { State.auditEvents = await fetchApi('/api/activity/history?limit=100'); } catch { State.auditEvents = State.events; } renderAuditHistory(); $('#auditDialog').showModal(); }
function agentStateLabel(agent) { if (agent.visualPhase === 'commuting') return 'EN RUTA'; if (agent.simulatedWorking) return 'SIMULANDO'; return agent.status === 'working' ? 'TRABAJANDO' : agent.idle_mode === 'Sleep' ? 'DESCANSANDO' : agent.idle_mode === 'Coffee' ? 'EN PAUSA' : 'RECARGANDO'; }
function agentActivityCopy(agent) { if (agent.simulatedWorking) return agent.visualPhase === 'commuting' ? 'Recorrido de prueba hacia el despacho. No se ha creado ninguna misión.' : 'En su puesto durante la simulación visual. No se consumen tokens.'; if (agent.visualPhase === 'commuting') return `Ha dejado su descanso y va hacia su puesto para ${agent.action}.`; if (agent.status === 'working') return `Está en su estación: ${agent.action}. El trabajo ya está en marcha.`; if (agent.idle_mode === 'Sleep') return 'Está recuperando energía en la zona de descanso y sigue disponible para una orden.'; if (agent.idle_mode === 'Coffee') return 'Está tomando café en la sala común, atento a la siguiente misión.'; return 'Está en la sala común recargando antes de asumir una nueva tarea.'; }
function createAgentWatchCard(agent) { return `<article class="AgentWatchCard" data-watch-agent-id="${agent.id}"><div class="AgentWatchTop"><span class="AgentSignal"></span><strong></strong><em></em></div><div class="AgentMiniScene"><i class="MiniGlow"></i><i class="MiniDesk"></i><i class="AgentFeedSlime"></i><i class="MiniParticles"></i></div><div class="AgentWatchBottom"><span class="AgentWatchRole"></span><span class="AgentWatchTokens"></span></div><button class="AgentInfoButton" type="button" data-agent-info="${agent.id}" aria-expanded="false">VER ACTIVIDAD <span>+</span></button><section class="AgentDetailPopover" hidden><button class="AgentPopoverClose" type="button" data-agent-info="${agent.id}" aria-label="Cerrar detalle">×</button><b></b><p></p><small></small></section></article>`; }
function updateAgentWatchCard(card, agent) { const state = agent.visualPhase === 'commuting' ? 'Commuting' : agent.status === 'working' || agent.simulatedWorking ? 'Working' : `Resting ${agent.idle_mode}`; const usage = Math.round((agent.tokens_used / agent.token_budget) * 100); const expanded = State.openAgentId === agent.id; card.className = `AgentWatchCard ${state}${expanded ? ' IsExpanded' : ''}`; card.dataset.break = BreakActivities[agent.id] || 'coffee'; card.style.setProperty('--agent-tone', agent.tone); card.style.setProperty('--hue', agent.hue || '0deg'); card.querySelector('.AgentWatchTop strong').textContent = agent.name; card.querySelector('.AgentWatchTop em').textContent = agentStateLabel(agent); card.querySelector('.AgentWatchRole').textContent = agent.role; card.querySelector('.AgentWatchTokens').textContent = `${usage}% TOKENS`; const button = card.querySelector('.AgentInfoButton'); button.setAttribute('aria-expanded', String(expanded)); button.querySelector('span').textContent = expanded ? '−' : '+'; const popup = card.querySelector('.AgentDetailPopover'); popup.hidden = !expanded; popup.querySelector('b').textContent = `${agent.name} · ${agentStateLabel(agent)}`; popup.querySelector('p').textContent = agentActivityCopy(agent); popup.querySelector('small').textContent = `${formatNumber(agent.tokens_used)} / ${formatNumber(agent.token_budget)} tokens · esfuerzo ${uppercase(agent.reasoning_effort)}`; }
function renderAgentWatchPanels() { const rails = [$('#agentWatchRailLeft'), $('#agentWatchRailRight')]; const split = Math.ceil(State.agents.length / 2); [State.agents.slice(0, split), State.agents.slice(split)].forEach((agents, index) => { const rail = rails[index]; agents.forEach((agent) => { let card = rail.querySelector(`[data-watch-agent-id="${agent.id}"]`); if (!card) { rail.insertAdjacentHTML('beforeend', createAgentWatchCard(agent)); card = rail.querySelector(`[data-watch-agent-id="${agent.id}"]`); } updateAgentWatchCard(card, agent); }); }); }
function routeToRoom(agent, zone) {
  if (agent.route) { agent.nextRoomZone = zone; return; }
  if (agent.roomZone === zone) return;
  const station = RoomStations[agent.id] || Object.values(RoomStations)[State.agents.indexOf(agent) % Object.keys(RoomStations).length];
  const corridor = zone === 'work' ? station.door : [...station.door].reverse();
  const destination = zone === 'work' ? agent.work : agent.sleep;
  agent.route = zone === 'work'
    ? [[...(agent.position || agent.sleep)], [49,48], ...corridor, [...destination]]
    : [[...(agent.position || agent.work)], ...corridor, [49,48], [...destination]];
  agent.routeIndex = 0;
  agent.segmentStart = Date.now();
  agent.routeTarget = zone;
  agent.visualPhase = 'commuting';
  agent.moving = true;
}
function advanceRoomRoutes() {
  const now = Date.now();
  const world = $('#roomWorld');
  State.agents.forEach((agent) => {
    if (!agent.route) return;
    // Wall-clock time lets a route catch up after reload or a backgrounded tab.
    for (let step = 0; agent.route && step < 24; step++) {
      const start = agent.route[agent.routeIndex];
      const end = agent.route[agent.routeIndex + 1];
      const distance = Math.hypot(end[0] - start[0], end[1] - start[1]);
      const duration = Math.max(300, distance * 115);
      const progress = Math.max(0, Math.min(1, (now - agent.segmentStart) / duration));
      agent.position = [start[0] + (end[0] - start[0]) * progress, start[1] + (end[1] - start[1]) * progress];
      if (progress < 1) break;
      agent.routeIndex += 1;
      agent.segmentStart += duration;
      if (agent.routeIndex === agent.route.length - 1) {
        agent.roomZone = agent.routeTarget;
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
function createSlimeUnit(agent) { return `<div class="SlimeUnit" data-agent-id="${agent.id}"><i class="WorkLabel"></i><i class="SlimeSprite" aria-hidden="true"></i><strong></strong></div>`; }
function updateSlimeUnit(element, agent) { const commuting = agent.visualPhase === 'commuting'; const [x, y] = agent.position || agent.sleep; const stateClass = commuting ? `Commuting ${agent.idle_mode}` : agent.status === 'working' || agent.simulatedWorking ? 'Working' : `Resting ${agent.idle_mode}${agent.moving ? ' Moving' : ''}`; element.className = `SlimeUnit ${stateClass}`; element.dataset.break = BreakActivities[agent.id] || 'coffee'; element.style.setProperty('--tone', agent.tone); element.style.setProperty('--hue', agent.hue || '0deg'); element.style.left = `calc(${x}% - 29px)`; element.style.top = `calc(${y}% - 62px)`; element.style.zIndex = String(5 + Math.round(y)); element.querySelector('.WorkLabel').textContent = commuting ? 'en ruta' : agent.action; element.querySelector('strong').textContent = agent.name; }
function renderSlimeRoom() { const world = $('#roomWorld'); world.style.setProperty('--room-zoom', State.roomZoom); world.style.setProperty('--room-pan-x', `${State.roomPan}%`); world.style.setProperty('--room-pan-y', `${State.roomPanY}%`); State.agents.forEach((agent) => { let element = world.querySelector(`[data-agent-id="${agent.id}"]`); if (!element) { world.insertAdjacentHTML('beforeend', createSlimeUnit(agent)); element = world.querySelector(`[data-agent-id="${agent.id}"]`); } updateSlimeUnit(element, agent); }); const activeNames = State.agents.filter((agent) => agent.status === 'working').map((agent) => agent.name); $('#roomStatus').textContent = State.roomSimulation ? 'SIMULACIÓN VISUAL · TODOS AL TRABAJO' : activeNames.length ? activeNames.join(' + ') : 'Todos descansando'; }
const RoomVisualFields = ['position', 'sleep', 'roomZone', 'route', 'routeIndex', 'segmentStart', 'routeTarget', 'nextRoomZone', 'moving', 'visualPhase', 'loungeStep'];
function startRoomSimulation() {
  if (State.roomSimulation || !State.agents.length) return;
  saveRoomState();
  State.roomSimulation = new Map(State.agents.map((agent) => {
    const visual = Object.fromEntries(RoomVisualFields.map((field) => [field, agent[field]]));
    return [agent.id, structuredClone(visual)];
  }));
  State.agents.forEach((agent) => {
    const station = RoomStations[agent.id] || Object.values(RoomStations)[State.agents.indexOf(agent) % Object.keys(RoomStations).length];
    agent.route = null;
    agent.nextRoomZone = undefined;
    agent.position = [...station.rest];
    agent.sleep = [...station.rest];
    agent.roomZone = 'rest';
    agent.simulatedWorking = true;
    routeToRoom(agent, 'work');
  });
  const button = $('#simulateAll');
  button.textContent = 'VOLVER AL DIRECTO';
  button.classList.add('IsRunning');
  renderDashboard();
}
function stopRoomSimulation() {
  if (!State.roomSimulation) return;
  State.agents.forEach((agent) => {
    const previous = State.roomSimulation.get(agent.id);
    if (previous) RoomVisualFields.forEach((field) => { if (previous[field] === undefined) delete agent[field]; else agent[field] = previous[field]; });
    delete agent.simulatedWorking;
  });
  State.roomSimulation = null;
  const button = $('#simulateAll');
  button.textContent = 'SIMULAR: TODOS AL TRABAJO';
  button.classList.remove('IsRunning');
  if (State.latestDashboard) consumeDashboard(State.latestDashboard);
  else renderDashboard();
  saveRoomState();
}
function controlRoomCamera(command) { if (command === 'in') State.roomZoom = Math.min(1.14, +(State.roomZoom + .07).toFixed(2)); if (command === 'out') State.roomZoom = Math.max(.9, +(State.roomZoom - .07).toFixed(2)); if (command === 'left') State.roomPan = Math.max(-9, State.roomPan - 3); if (command === 'right') State.roomPan = Math.min(9, State.roomPan + 3); if (command === 'up') State.roomPanY = Math.max(-8, State.roomPanY - 3); if (command === 'down') State.roomPanY = Math.min(8, State.roomPanY + 3); if (command === 'center') { State.roomZoom = 1; State.roomPan = 0; State.roomPanY = 0; } renderSlimeRoom(); }
function renderDashboard() { renderControlPanel(); renderMetricsPanel(); renderCodexUsage(); renderActivityLog(); renderSlimeRoom(); renderAgentWatchPanels(); }
function updateConnectionLabel() { $('#apiStatus').textContent = State.connected ? '● API CONECTADA' : '● API DEMO'; $('#apiStatus').style.color = State.connected ? 'var(--acid)' : 'var(--cyan)'; }
function updateDigitalClock() { const now = new Date(); $('#digitalTime').textContent = now.toLocaleTimeString('es-ES', {hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false}); const date = new Intl.DateTimeFormat('es-ES', {weekday:'long', day:'2-digit', month:'short', year:'numeric'}).format(now).replace('.', '').toUpperCase(); $('#digitalDate').textContent = date.replace(',', ' ·'); }
function triggerWorkAnimation(agentIds) { State.agents.filter((agent) => agentIds.includes(agent.id)).forEach((agent) => { agent.status = 'working'; routeToRoom(agent, 'work'); }); renderSlimeRoom(); }
function detectRemoteDispatches(events) { const dispatches = events.filter((event) => event.kind === 'mission_dispatched'); if (!State.dashboardReady) { dispatches.forEach((event) => State.knownDispatches.add(event.id)); State.dashboardReady = true; return; } const agentIds = dispatches.filter((event) => !State.knownDispatches.has(event.id)).map((event) => { State.knownDispatches.add(event.id); return State.agents.find((agent) => agent.name === event.agent)?.id; }).filter(Boolean); if (!State.roomSimulation) triggerWorkAnimation([...new Set(agentIds)]); }
function consumeDashboard(dashboard) { State.latestDashboard = dashboard; dashboard.agents.forEach((remoteAgent) => { let localAgent = State.agents.find((agent) => agent.id === remoteAgent.id); const isNew = !localAgent; if (isNew) { localAgent = buildVisualAgent(remoteAgent); State.agents.push(localAgent); } const status = remoteAgent.status === 'running' ? 'working' : 'sleeping'; if (!State.roomSimulation && !localAgent.roomStateRestored && !localAgent.route && status === 'working' && (State.dashboardReady === false || isNew)) { localAgent.position = [...localAgent.work]; localAgent.roomZone = 'work'; localAgent.visualPhase = 'working'; } Object.assign(localAgent, remoteAgent, {status, hue: remoteAgent.display_hue || localAgent.hue, action: remoteAgent.current_task === 'En espera' ? (remoteAgent.default_action || localAgent.action) : remoteAgent.current_task}); if (!State.roomSimulation) routeToRoom(localAgent, status === 'working' ? 'work' : 'rest'); }); const remoteIds = new Set(dashboard.agents.map((agent) => agent.id)); State.agents = State.agents.filter((agent) => remoteIds.has(agent.id)); if (!State.agents.some((agent) => agent.id === State.selectedAgentId)) State.selectedAgentId = State.agents[0]?.id; detectRemoteDispatches(dashboard.events || []); State.events = dashboard.events || []; State.connected = true; State.lastTelemetryAt = new Date(); updateConnectionLabel(); renderDashboard(); }
async function syncDashboard() { consumeDashboard(await fetchApi('/api/dashboard')); }
function connectLiveStream() { if (State.eventSource) return; const stream = new EventSource(`${API_URL}/api/stream`); State.eventSource = stream; stream.onmessage = (event) => { try { consumeDashboard(JSON.parse(event.data)); } catch {} }; stream.onerror = () => { stream.close(); if (State.eventSource === stream) { State.eventSource = null; setTimeout(connectLiveStream, 2500); } }; }
async function checkForDeployment() { const response = await fetch(`app-version.json?check=${Date.now()}`, {cache:'no-store'}); if (!response.ok) return; const {buildId} = await response.json(); if (State.buildId && State.buildId !== buildId) { window.location.reload(); return; } State.buildId = buildId; }
async function syncCodexUsage() { const usage = await fetchApi('/api/codex-usage'); State.codexUsage = usage; renderCodexUsage(); renderCodexUsageChart(); }
async function syncUsageSeries() { State.agentUsageSeries = await fetchApi('/api/usage-series?minutes=60'); renderAgentUsageChart(); }
function runLocalTelemetry() { if (State.connected) return; let changed = false; State.agents.forEach((agent) => { if (agent.status !== 'working') return; const rates = {low: 2, medium: 4, high: 7, xhigh: 11}; agent.tokens_used = Math.min(agent.token_budget, agent.tokens_used + rates[agent.reasoning_effort]); if (agent.tokens_used >= agent.token_budget) agent.status = 'sleeping'; changed = true; }); if (changed) { State.lastTelemetryAt = new Date(); renderMetricsPanel(); } }
function makeSlimesWander() { if (State.roomSimulation) return; State.agents.filter((agent) => agent.status !== 'working' && !agent.route && agent.roomZone === 'rest').forEach((agent) => { const stops = LoungeRoutes[agent.id] || SharedRestStops; agent.loungeStep = ((agent.loungeStep ?? -1) + 1) % stops.length; agent.sleep = [...stops[agent.loungeStep]]; agent.route = [[...agent.position], [...agent.sleep]]; agent.routeIndex = 0; agent.segmentStart = Date.now(); agent.routeTarget = 'rest'; agent.moving = true; }); }
function localRouteMission(prompt) { const value = prompt.toLowerCase(); const selected = ['director','nexus']; if (/investiga|fuente|busca|compet|analiza/.test(value)) selected.push('scout'); if (/crea|constru|código|codigo|web|diseña|disena/.test(value)) selected.push('forge'); if (/revisa|calidad|error|test|riesgo/.test(value)) selected.push('sentinel'); if (/diseño|diseno|visual|estética|estetica|ui|ux|pixel|animación|animacion|ilustración|ilustracion|arte|estilo|interfaz|layout/.test(value)) selected.push('muse'); return [...new Set(selected.length === 2 ? [...selected, 'scout'] : selected)]; }
async function submitMission(event) { event.preventDefault(); const input = $('#missionInput'); const prompt = input.value.trim(); if (!prompt) return; if (State.roomSimulation) stopRoomSimulation(); let assigned = localRouteMission(prompt); State.agents.forEach((agent) => { if (!assigned.includes(agent.id)) { agent.status = 'sleeping'; routeToRoom(agent, 'rest'); } }); triggerWorkAnimation(assigned); $('#missionSummary').textContent = 'Trabajo iniciado. Los slimes van hacia su despacho…'; input.value = ''; renderDashboard(); try { const result = await fetchApi('/api/dispatch', {method:'POST', body:JSON.stringify({prompt})}); assigned = result.agent_ids; triggerWorkAnimation(assigned); $('#missionSummary').textContent = result.plan; } catch { $('#missionSummary').textContent = 'Misión iniciada en modo demo.'; } }
async function saveAgentControls() { const agent = getSelectedAgent(); const {dirty, ...draft} = getControlDraft(agent); draft.token_budget = Number($('#budgetInput').value); if (draft.token_budget < 500 || draft.token_budget > 24000) { $('#controlFeedback').textContent = 'El límite debe estar entre 500 y 24.000 tokens.'; return; } try { const updated = await fetchApi(`/api/agents/${agent.id}/controls`, {method:'POST', body:JSON.stringify(draft)}); Object.assign(agent, updated); State.controlDrafts.delete(agent.id); $('#controlFeedback').textContent = `${agent.provider} · ${agent.model || 'sin modelo'} guardado.`; } catch (error) { if (!State.connected) { Object.assign(agent, draft); State.controlDrafts.delete(agent.id); $('#controlFeedback').textContent = 'Ajuste solo local: conecta la API para guardarlo.'; } else { $('#controlFeedback').textContent = `No se guardó: ${error.message}`; } } renderDashboard(); }
function bindInteractions() { $('#agentSelect').addEventListener('change', (event) => { State.selectedAgentId = event.target.value; $('#controlFeedback').textContent = ''; renderControlPanel(); }); $('#budgetInput').addEventListener('input', (event) => { const draft = getControlDraft(getSelectedAgent()); draft.token_budget = Number(event.target.value); draft.dirty = true; }); $('#providerSelect').addEventListener('change', (event) => { const draft = getControlDraft(getSelectedAgent()); draft.provider = event.target.value; draft.model = modelsFor(draft.provider)[0] || ''; draft.dirty = true; renderControlPanel(); }); $('#modelSelect').addEventListener('change', (event) => { const draft = getControlDraft(getSelectedAgent()); draft.model = event.target.value; draft.dirty = true; }); $('#effortSelector').addEventListener('click', (event) => { const level = event.target.dataset.effort; if (!level) return; const draft = getControlDraft(getSelectedAgent()); draft.reasoning_effort = level; draft.dirty = true; renderControlPanel(); }); $('#saveControls').addEventListener('click', saveAgentControls); $('#openCustomizer').addEventListener('click', openCustomizer); $('#closeCustomizer').addEventListener('click', () => $('#customizerDialog').close()); $('#cancelCustomizer').addEventListener('click', () => $('#customizerDialog').close()); $('#customizerForm').addEventListener('submit', saveCustomizer); $('#profileAgentSelect').addEventListener('change', (event) => { State.profileAgentId = event.target.value; renderCustomizer(); }); ['profileName','profileRole','profileAction','profileTone','profileHue','profileActions'].forEach((id) => $(`#${id}`).addEventListener('input', previewCustomizer)); $('#missionForm').addEventListener('submit', submitMission); $('#refreshCodexUsage').addEventListener('click', () => syncCodexUsage().catch(() => {})); $('#openAudit').addEventListener('click', () => openAuditHistory()); $('#closeAudit').addEventListener('click', () => $('#auditDialog').close()); document.querySelector('.LiveOpsLayout').addEventListener('click', (event) => { const camera = event.target.closest('[data-camera]'); if (camera) { controlRoomCamera(camera.dataset.camera); return; } const button = event.target.closest('[data-agent-info]'); if (!button) return; const id = button.dataset.agentInfo; State.openAgentId = State.openAgentId === id ? null : id; renderAgentWatchPanels(); }); }
function bindAccess() { $('#openAccess').addEventListener('click', openAccess); $('#closeAccess').addEventListener('click', () => $('#accessDialog').close()); $('#activeUserSelect').addEventListener('change', (event) => { State.operatorId = event.target.value; localStorage.setItem('slimeops-operator', State.operatorId); renderAccess(); syncDashboard().catch(() => {}); }); $('#roleForm').addEventListener('submit', async (event) => { event.preventDefault(); const name = $('#newRoleName').value.trim(); const permissions = $('#newRolePermissions').value.split(',').map((item) => item.trim()).filter(Boolean); if (!name || !permissions.length) return; State.access = await fetchApi('/api/access/roles', {method:'POST', body:JSON.stringify({name, permissions})}); renderAccess(); }); $('#userForm').addEventListener('submit', async (event) => { event.preventDefault(); const name = $('#newUserName').value.trim(); if (!name) return; State.access = await fetchApi('/api/access/users', {method:'POST', body:JSON.stringify({name, role_id:$('#newUserRole').value})}); renderAccess(); }); }
$('#simulateAll').addEventListener('click', () => State.roomSimulation ? stopRoomSimulation() : startRoomSimulation());
bindInteractions(); bindAccess(); bindAgentCreation(); renderDashboard(); renderAgentUsageChart(); renderCodexUsageChart(); requestAnimationFrame(advanceRoomRoutes); updateDigitalClock(); syncDashboard().catch(() => { updateConnectionLabel(); }); syncUsageSeries().catch(() => {}); syncModelCatalog().catch(() => {}); connectLiveStream(); syncCodexUsage().catch(() => {}); checkForDeployment().catch(() => {}); setInterval(() => syncDashboard().catch(() => {}), 2000); setInterval(() => syncUsageSeries().catch(() => {}), 15000); setInterval(() => syncCodexUsage().catch(() => {}), 60000); setInterval(() => checkForDeployment().catch(() => {}), 25000); setInterval(runLocalTelemetry, 1000); setInterval(makeSlimesWander, 4200); setInterval(saveRoomState, 500); setInterval(updateDigitalClock, 1000); window.addEventListener('pagehide', saveRoomState); document.addEventListener('visibilitychange', () => { if (document.hidden) saveRoomState(); else { syncDashboard().catch(() => {}); connectLiveStream(); } });
