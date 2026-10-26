// Occupancy is a fraction of agents, never a ratio of tokens to a soft budget.
export function operationalHealth(agents) {
  const statuses = agents.map(
    (agent) => agent.operationalStatus || (agent.status === 'working' ? 'running' : 'standby'),
  );
  const active = statuses.filter((status) =>
    ['active', 'running', 'thinking'].includes(status),
  ).length;
  const available = statuses.filter((status) => status === 'standby').length;
  const percent = (count) => (statuses.length ? Math.round((count * 100) / statuses.length) : 0);
  return {
    active,
    available,
    occupancy: percent(active),
    availability: percent(available),
    status: statuses.includes('error')
      ? 'ERROR'
      : statuses.includes('blocked')
        ? 'BLOQUEO'
        : active
          ? 'ACTIVO'
          : 'EN ESPERA',
    tokens: agents.reduce((total, agent) => total + Math.max(0, Number(agent.tokens_used) || 0), 0),
  };
}
