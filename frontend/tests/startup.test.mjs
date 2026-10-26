import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { probeService, waitForService, stopChild } from '../../scripts/local-services.mjs';

async function service(t, handler) {
  const server = createServer(handler);
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  t.after(() => {
    server.closeAllConnections();
    server.close();
  });
  return `http://127.0.0.1:${server.address().port}`;
}
test('launcher reuses only an identified SlimeOps API', async (t) => {
  const own = await service(t, (req, res) => {
    res.setHeader('Content-Type', 'application/json');
    res.end('{"app":"slimeops","status":"ok"}');
  });
  const foreign = await service(t, (req, res) => res.end('{"status":"ok"}'));
  assert.equal(await probeService(own, 'api'), 'ready');
  assert.equal(await probeService(foreign, 'api'), 'foreign');
});
test('launcher rejects malformed health and unrelated frontend pages', async (t) => {
  const foreign = await service(t, (req, res) => res.end('<html>other application</html>'));
  assert.equal(await probeService(foreign, 'api'), 'foreign');
  assert.equal(await probeService(foreign, 'front'), 'foreign');
  const own = await service(t, (req, res) =>
    res.end('<title>SlimeOps</title><div id="slimeRoom"></div>'),
  );
  assert.equal(await probeService(own, 'front'), 'ready');
});
test('launcher can cancel waiting for readiness without hanging', async () => {
  await assert.rejects(
    () => waitForService('http://127.0.0.1:9999', 'api', { stopped: () => true }),
    /cancelado/,
  );
});
test('launcher terminates only its child process and accepts an already closed child', async () => {
  const child = spawn(
    process.execPath,
    ['--preserve-symlinks-main', '-e', 'setInterval(()=>{},1000)'],
    { stdio: 'ignore', windowsHide: true },
  );
  await new Promise((resolve, reject) => {
    child.once('spawn', resolve);
    child.once('error', reject);
  });
  const exited = new Promise((resolve) => child.once('exit', resolve));
  await stopChild(child);
  await exited;
  assert.ok(child.exitCode !== null || child.signalCode !== null);
  await stopChild(child);
});
