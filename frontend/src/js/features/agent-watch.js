import { agentActivityCopy, agentStateLabel, visualStatus } from '../agents/model.js';
import { BreakActivities } from '../config.js';
import { $, formatNumber, uppercase } from '../dom.js';
import { State } from '../state.js';

function createAgentWatchCard(agent) {
  return `<article class="AgentWatchCard" data-watch-agent-id="${agent.id}"><div class="AgentWatchTop"><span class="AgentSignal"></span><strong></strong><em></em></div><div class="AgentMiniScene"><i class="MiniGlow"></i><i class="MiniDesk"></i><i class="AgentFeedSlime"></i><i class="MiniParticles"></i></div><div class="AgentWatchBottom"><span class="AgentWatchRole"></span><span class="AgentWatchTokens"></span></div><button class="AgentInfoButton" type="button" data-agent-info="${agent.id}" aria-expanded="false">VER ACTIVIDAD <span>+</span></button><section class="AgentDetailPopover" hidden><button class="AgentPopoverClose" type="button" data-agent-info="${agent.id}" aria-label="Cerrar detalle">×</button><b></b><p></p><small></small></section></article>`;
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
  const split = Math.ceil(State.agents.length / 2);
  [State.agents.slice(0, split), State.agents.slice(split)].forEach((agents, index) => {
    const rail = rails[index];
    agents.forEach((agent) => {
      let card = rail.querySelector(`[data-watch-agent-id="${agent.id}"]`);
      if (!card) {
        rail.insertAdjacentHTML('beforeend', createAgentWatchCard(agent));
        card = rail.querySelector(`[data-watch-agent-id="${agent.id}"]`);
      }
      updateAgentWatchCard(card, agent);
    });
  });
}

export { createAgentWatchCard, updateAgentWatchCard, renderAgentWatchPanels };
