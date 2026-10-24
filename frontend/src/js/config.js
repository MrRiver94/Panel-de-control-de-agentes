const API_URL = 'http://127.0.0.1:8000';

const EffortLevels = ['low', 'medium', 'high', 'xhigh'];

const DemoAgents = [
  {
    id: 'director',
    name: 'DIRECTOR',
    role: 'Dirección',
    tone: '#ffd166',
    hue: '-100deg',
    tokens_used: 0,
    token_budget: 6000,
    reasoning_effort: 'high',
    status: 'sleeping',
    idle_mode: 'Coffee',
    sleep: [36, 44],
    work: [80, 25],
    action: 'priorizando',
  },
  {
    id: 'nexus',
    name: 'NEXUS',
    role: 'Coordinación',
    tone: '#d9f45a',
    hue: '68deg',
    tokens_used: 0,
    token_budget: 8000,
    reasoning_effort: 'high',
    status: 'sleeping',
    idle_mode: 'Eating',
    sleep: [54, 48],
    work: [51, 17],
    action: 'planificando',
  },
  {
    id: 'scout',
    name: 'SCOUT',
    role: 'Investigación',
    tone: '#79e8ee',
    hue: '0deg',
    tokens_used: 0,
    token_budget: 5500,
    reasoning_effort: 'medium',
    status: 'sleeping',
    idle_mode: 'Sleep',
    sleep: [44, 71],
    work: [18, 28],
    action: 'investigando',
  },
  {
    id: 'forge',
    name: 'FORGE',
    role: 'Construcción',
    tone: '#ff789d',
    hue: '135deg',
    tokens_used: 0,
    token_budget: 7000,
    reasoning_effort: 'medium',
    status: 'sleeping',
    idle_mode: 'Sleep',
    sleep: [58, 71],
    work: [20, 64],
    action: 'construyendo',
  },
  {
    id: 'sentinel',
    name: 'SENTINEL',
    role: 'Calidad',
    tone: '#ab8cff',
    hue: '230deg',
    tokens_used: 0,
    token_budget: 4500,
    reasoning_effort: 'low',
    status: 'sleeping',
    idle_mode: 'Coffee',
    sleep: [39, 34],
    work: [79, 63],
    action: 'revisando',
  },
  {
    id: 'muse',
    name: 'MUSE',
    role: 'Dirección de arte',
    tone: '#ffaf5f',
    hue: '-45deg',
    tokens_used: 0,
    token_budget: 6200,
    reasoning_effort: 'high',
    status: 'sleeping',
    idle_mode: 'Eating',
    sleep: [55, 34],
    work: [49, 33],
    action: 'diseñando',
  },
];

const BreakActivities = {
  director: 'phone',
  nexus: 'coffee',
  scout: 'gameboy',
  forge: 'talk',
  sentinel: 'coffee',
  muse: 'talk',
};

const WorkStatuses = new Set(['active', 'running', 'thinking']);

const WorkActionCycle = [
  { id: 'typing', label: 'programando', glyph: '⌨' },
  { id: 'analyzing', label: 'analizando', glyph: '⌕' },
  { id: 'thinking', label: 'pensando', glyph: '?' },
  { id: 'reading', label: 'leyendo', glyph: '▤' },
  { id: 'debugging', label: 'depurando', glyph: '!' },
  { id: 'planning', label: 'planificando', glyph: '✎' },
  { id: 'testing', label: 'probando', glyph: '✓' },
  { id: 'reviewing', label: 'revisando', glyph: '◉' },
  { id: 'writing', label: 'documentando', glyph: '✦' },
  { id: 'building', label: 'construyendo', glyph: '⚙' },
  { id: 'searching', label: 'investigando', glyph: '⌖' },
  { id: 'presenting', label: 'coordinando', glyph: '↗' },
];

const FallbackModelCatalog = {
  providers: [
    { id: 'codex', label: 'Codex / OpenAI', models: ['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna'] },
    {
      id: 'anthropic',
      label: 'Anthropic / Claude',
      models: ['claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5-20251001'],
    },
  ],
  source: 'suggested',
};

const RoomStations = {
  director: { rest: [6, 35], desk: [51, 33], fieldLane: [51, 33] },
  nexus: { rest: [18, 35], desk: [67, 33], fieldLane: [67, 33] },
  scout: { rest: [29, 35], desk: [87, 33], fieldLane: [87, 33] },
  forge: { rest: [6, 56], desk: [51, 68], fieldLane: [51, 68] },
  sentinel: { rest: [18, 56], desk: [67, 68], fieldLane: [67, 68] },
  muse: { rest: [29, 56], desk: [87, 68], fieldLane: [87, 68] },
};

const CaveFloor = [
  [1, 31],
  [5, 27],
  [27, 27],
  [33, 32],
  [37, 40],
  [36, 45],
  [40, 49],
  [37, 54],
  [35, 61],
  [29, 66],
  [7, 67],
  [1, 61],
];

const RoomCorridor = { left: 31, right: 49, top: 39, bottom: 59 };

const MeadowFloor = [
  [40, 12],
  [91, 12],
  [96, 18],
  [98, 32],
  [98, 76],
  [94, 86],
  [40, 86],
];

const LoungeVisits = [
  [0, 0],
  [0, -2],
  [0, 2],
  [0, -1],
  [0, 1],
];

const RoomStateKey = 'slimeops-room-v13';

const RestActivities = new Set(['stroll', 'eating', 'coffee']);

const RoomVisualFields = [
  'position',
  'sleep',
  'roomZone',
  'route',
  'routeIndex',
  'segmentStart',
  'routeTarget',
  'nextRoomZone',
  'moving',
  'visualPhase',
  'loungeStep',
  'restUntil',
  'restActivity',
];

DemoAgents.forEach((agent) => {
  agent.tokens_used = 0;
  agent.sleep = [...RoomStations[agent.id].rest];
  agent.work = [...RoomStations[agent.id].desk];
  agent.position = [...agent.sleep];
  agent.roomZone = 'rest';
  agent.provider = 'codex';
  agent.model = '';
});

export {
  API_URL,
  EffortLevels,
  DemoAgents,
  BreakActivities,
  WorkStatuses,
  WorkActionCycle,
  FallbackModelCatalog,
  RoomStations,
  CaveFloor,
  RoomCorridor,
  MeadowFloor,
  LoungeVisits,
  RoomStateKey,
  RestActivities,
  RoomVisualFields,
};
