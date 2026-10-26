import assert from 'node:assert/strict';
import { copyFile, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';

test('build is reproducible and check detects stale output without overwriting it', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'slimeops-build-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, 'frontend/src/assets'), { recursive: true });
  const builder = join(root, 'frontend/build.mjs');
  await copyFile(new URL('../build.mjs', import.meta.url), builder);
  await writeFile(join(root, 'frontend/src/index.html'), '<script src="app.js"></script>');
  await writeFile(join(root, 'frontend/src/app.js'), 'const asset = "assets/marker.svg";');
  await writeFile(join(root, 'frontend/src/assets/marker.svg'), '<svg/>');
  const run = (...args) =>
    spawnSync(
      process.execPath,
      ['--preserve-symlinks', '--preserve-symlinks-main', builder, ...args],
      {
        encoding: 'utf8',
        windowsHide: true,
        timeout: 10000,
      },
    );
  assert.equal(run().status, 0);
  const firstVersion = await readFile(join(root, 'dist/app-version.json'), 'utf8');
  assert.equal(run().status, 0);
  assert.equal(await readFile(join(root, 'dist/app-version.json'), 'utf8'), firstVersion);
  assert.equal(run('--check').status, 0);
  await writeFile(join(root, 'dist/app.js'), 'stale publication');
  const check = run('--check');
  assert.equal(check.status, 1);
  assert.match(check.stderr, /app\.js/);
  assert.equal(await readFile(join(root, 'dist/app.js'), 'utf8'), 'stale publication');
  assert.equal(run().status, 0);
  assert.equal(run('--check').status, 0);
});
