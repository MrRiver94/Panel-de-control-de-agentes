import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { SourceTextModule, SyntheticModule, createContext } from 'node:vm';

async function client(fetch, timers = {}) {
  const context = createContext({
    fetch,
    AbortController,
    Error,
    setTimeout: timers.setTimeout || setTimeout,
    clearTimeout: timers.clearTimeout || clearTimeout,
  });
  const module = new SourceTextModule(
    readFileSync(new URL('../src/js/services/api.js', import.meta.url), 'utf8'),
    { context },
  );
  await module.link((specifier) => {
    const name = specifier.includes('config') ? 'API_URL' : 'State';
    return new SyntheticModule(
      [name],
      function () {
        this.setExport(name, name === 'API_URL' ? 'http://local' : { operatorId: 'test-operator' });
      },
      { context },
    );
  });
  await module.evaluate();
  return module.namespace.fetchApi;
}

test('API sends operator, JSON and the supplied body', async () => {
  let request;
  const fetchApi = await client(async (url, options) => {
    request = { url, options };
    return { ok: true, json: async () => ({ saved: true }) };
  });
  const result = await fetchApi('/api/dispatch', {
    method: 'POST',
    body: '{"request_id":"same-request"}',
  });
  assert.equal(request.options.headers['X-Operator-Id'], 'test-operator');
  assert.equal(request.options.body, '{"request_id":"same-request"}');
  assert.equal(result.saved, true);
});
test('API exposes useful server detail and handles non-JSON errors', async () => {
  const fetchApi = await client(async () => ({
    ok: false,
    status: 409,
    text: async () => ' {"detail":"Already busy"}',
  }));
  await assert.rejects(() => fetchApi('/api/dispatch'), /Already busy/);
  const unavailable = await client(async () => ({
    ok: false,
    status: 502,
    text: async () => '<html>gateway</html>',
  }));
  await assert.rejects(() => unavailable('/api/dispatch'), /Error 502/);
});
test('API timeout aborts transport and explains safe resubmission', async () => {
  let cleared = false;
  const fetchApi = await client(
    (url, { signal }) =>
      new Promise((resolve, reject) =>
        signal.addEventListener('abort', () =>
          reject(Object.assign(new Error(), { name: 'AbortError' })),
        ),
      ),
    {
      setTimeout: (callback) => setTimeout(callback, 1),
      clearTimeout: (id) => {
        cleared = true;
        clearTimeout(id);
      },
    },
  );
  await assert.rejects(() => fetchApi('/api/dispatch'), /identificador de envío/);
  assert.equal(cleared, true);
});
