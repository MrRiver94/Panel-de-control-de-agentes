import assert from 'node:assert/strict';
import { test } from 'node:test';
import { operationalHealth } from '../src/js/features/health.js';

test('large measured token totals do not become percentages of a soft budget', () => {
  const result = operationalHealth([
    { operationalStatus: 'standby', tokens_used: 498512, token_budget: 39700 },
  ]);
  assert.equal(result.occupancy, 0);
  assert.equal(result.availability, 100);
  assert.equal(result.tokens, 498512);
});
test('occupancy reflects active agents and availability excludes errors and blocks', () => {
  const result = operationalHealth(
    ['running', 'thinking', 'standby', 'error'].map((operationalStatus) => ({ operationalStatus })),
  );
  assert.equal(result.occupancy, 50);
  assert.equal(result.availability, 25);
  assert.equal(result.status, 'ERROR');
});
test('empty roster and explicit simulation never invent real load', () => {
  assert.equal(operationalHealth([]).occupancy, 0);
  assert.equal(
    operationalHealth([{ simulatedWorking: true, operationalStatus: 'standby' }]).occupancy,
    0,
  );
});
