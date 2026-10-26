import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';
import { test } from 'node:test';
import { pathToFileURL } from 'node:url';

const candidates = [
  process.env.SLIMEOPS_TEST_BROWSER,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/usr/bin/google-chrome',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
].filter(Boolean);
const browser = candidates.find((path) => existsSync(path));

test(
  'browser DOM regressions for access, agents, drafts and execution history',
  {
    skip:
      browser || process.env.SLIMEOPS_REQUIRE_BROWSER === '1'
        ? false
        : 'Chromium no disponible; configura SLIMEOPS_TEST_BROWSER para ejecutar las regresiones DOM.',
    timeout: 60000,
  },
  async (t) => {
    assert.ok(browser, 'Chromium es obligatorio en CI; configura SLIMEOPS_TEST_BROWSER.');
    const directory = await mkdtemp(join(tmpdir(), 'slimeops-dom-tests-'));
    t.after(() => rm(directory, { recursive: true, force: true, maxRetries: 4, retryDelay: 250 }));
    const source = new URL('../src/', import.meta.url);
    const fixture = new URL('./fixtures/dom-regressions.js', import.meta.url);
    const original = await readFile(new URL('index.html', source), 'utf8');
    const html = original
      .replace('<head>', `<head><base href="${source.href}">`)
      .replace(/<script type="module" src="app\.js"><\/script>/, '')
      .replace('</body>', `<script type="module" src="${fixture.href}"></script></body>`);
    const page = join(directory, 'regressions.html');
    await writeFile(page, html);
    const child = spawn(
      browser,
      [
        '--headless',
        '--disable-gpu',
        '--in-process-gpu',
        '--disable-software-rasterizer',
        '--no-first-run',
        '--disable-extensions',
        '--disable-background-networking',
        '--allow-file-access-from-files',
        `--user-data-dir=${join(directory, 'profile')}`,
        '--dump-dom',
        '--virtual-time-budget=5000',
        pathToFileURL(page).href,
      ],
      { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] },
    );
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (data) => {
      stdout += data;
    });
    child.stderr.on('data', (data) => {
      stderr += data;
    });
    const timeout = setTimeout(() => child.kill(), 45000);
    const code = await new Promise((resolveExit, reject) => {
      child.once('error', reject);
      child.once('close', resolveExit);
    }).finally(() => clearTimeout(timeout));
    assert.equal(code, 0, `Chromium no terminó: ${stderr.slice(-1500)}`);
    const encoded = stdout.match(/data-regression="([^"]*)"/)?.[1];
    assert.ok(encoded, `La página no terminó las comprobaciones: ${stderr.slice(-1500)}`);
    const results = JSON.parse(decodeURIComponent(encoded));
    assert.equal(results.length, 8, JSON.stringify(results));
    for (const result of results) {
      await t.test(result.name, () => assert.ok(result.ok, result.error));
    }
  },
);
