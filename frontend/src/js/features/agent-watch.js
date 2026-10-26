import { agentActivityCopy, agentStateLabel, visualStatus } from '../agents/model.js';
import { BreakActivities } from '../config.js';
import { $, formatNumber, uppercase } from '../dom.js';
import { State } from '../state.js';

function createAgentWatchCard(agent) {
  const card = document.createElement('article');
  card.className = 'AgentWatchCard';
  card.dataset.watchAgentId = agent.id;
  card.innerHTML =
    '<div class="AgentWatchTop"><span class="AgentSignal"></span><strong></strong><em></em></div><div class="AgentMiniScene"><i class="MiniGlow"></i><i class="MiniDesk"></i><i class="AgentFeedSlime"></i><i class="MiniParticles"></i></div><div class="AgentWatchBottom"><span class="AgentWatchRole"></span><span class="AgentWatchTokens"></span></div><button class="AgentInfoButton" type="button" aria-expanded="false">VER ACTIVIDAD <span>+</span></button><section class="AgentDetailPopover" hidden><button class="AgentPopoverClose" type="button" aria-label="Cerrar detalle">×</button><b></b><p></p><small></small></section>';
  card.querySelectorAll('button').forEach((button) => {
    button.dataset.agentInfo = agent.id;
  });
  return card;
}

function updateAgentWatchCard(card, agent) {
  const state =
    agent.visualPhase === 'commuting'
      ? 'Commuting'
      : agent.status === 'working' || agent.simulatedWorking
        ? 'Working'
        : `Resting ${agent.idle_mode}`;
  const expanded = State.openAgentId === agent.id;
  card.className = `AgentWatchCard ${state} Status${uppercase(visualStatus(agent)[0])}${visualStatus(agent).slice(1)}${expanded ? ' IsExpanded' : ''}`;
  card.dataset.break = BreakActivities[agent.id] || 'coffee';
  card.style.setProperty('--agent-tone', agent.tone);
  card.style.setProperty('--hue', agent.hue || '0deg');
  card.querySelector('.AgentWatchTop strong').textContent = agent.name;
  card.querySelector('.AgentWatchTop em').textContent = agentStateLabel(agent);
  card.querySelector('.AgentWatchRole').textContent = agent.role;
  card.querySelector('.AgentWatchTokens').textContent = `${formatNumber(agent.tokens_used)} tk`;
  const button = card.querySelector('.AgentInfoButton');
  button.setAttribute('aria-expanded', String(expanded));
  button.querySelector('span').textContent = expanded ? '−' : '+';
  const popup = card.querySelector('.AgentDetailPopover');
  popup.hidden = !expanded;
  popup.querySelector('b').textContent = `${agent.name} · ${agentStateLabel(agent)}`;
  popup.querySelector('p').textContent = agentActivityCopy(agent);
  popup.querySelector('small').textContent =
    `${formatNumber(agent.tokens_used)} tokens medidos · referencia orientativa ${formatNumber(agent.token_budget)} · esfuerzo ${uppercase(agent.reasoning_effort)}`;
}

function renderAgentWatchPanels() {
  const rails = [$('#agentWatchRailLeft'), $('#agentWatchRailRight')];
  const current = new Map();
  const ids = new Set(State.agents.map((agent) => agent.id));
  rails.forEach((rail) =>
    rail.querySelectorAll('[data-watch-agent-id]').forEach((card) => {
      const id = card.dataset.watchAgentId;
      if (!ids.has(id) || current.has(id)) card.remove();
      else current.set(id, card);
    }),
  );
  const split = Math.ceil(State.agents.length / 2);
  [State.agents.slice(0, split), State.agents.slice(split)].forEach((agents, index) => {
    const rail = rails[index];
    agents.forEach((agent, position) => {
      const card = current.get(agent.id) || createAgentWatchCard(agent);
      if (rail.children[position] !== card)
        rail.insertBefore(card, rail.children[position] || null);
      updateAgentWatchCard(card, agent);
    });
  });
}

export { createAgentWatchCard, updateAgentWatchCard, renderAgentWatchPanels };
