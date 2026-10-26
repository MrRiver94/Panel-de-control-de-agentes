import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { SourceTextModule, createContext } from 'node:vm';
import { test } from 'node:test';

test('portable app uses its own origin; development and file previews use the local API', async () => {
  const source = await readFile(new URL('../src/js/config.js', import.meta.url), 'utf8');
  for (const [location, expected] of [
    [
      { protocol: 'http:', port: '47831', origin: 'http://127.0.0.1:47831' },
      'http://127.0.0.1:47831',
    ],
    [{ protocol: 'http:', port: '4173', origin: 'http://127.0.0.1:4173' }, 'http://127.0.0.1:8000'],
    [{ protocol: 'file:', port: '', origin: 'null' }, 'http://127.0.0.1:8000'],
    [undefined, 'http://127.0.0.1:8000'],
  ]) {
    const module = new SourceTextModule(source, { context: createContext({ location }) });
    await module.link(() => {
      throw new Error('El catálogo local no debe tener dependencias.');
    });
    await module.evaluate();
    assert.equal(module.namespace.API_URL, expected);
  }
});
