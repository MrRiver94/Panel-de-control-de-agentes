import { mkdir, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import { dirname, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const project = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(project, 'frontend/src');
const output = resolve(project, 'dist');

async function listFiles(directory, prefix = '') {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const name = prefix + entry.name;
    if (entry.isDirectory())
      files.push(...(await listFiles(resolve(directory, entry.name), name + '/')));
    else if (entry.isFile()) files.push(name);
  }
  return files;
}

function outputPath(name) {
  const path = resolve(output, name);
  if (!path.startsWith(output + sep)) throw new Error(`Invalid build path: ${name}`);
  return path;
}

async function writeChangedFile(name, bytes) {
  const destination = outputPath(name);
  try {
    if ((await readFile(destination)).equals(bytes)) return;
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  await mkdir(dirname(destination), { recursive: true });
  const temporary = destination + '.build-tmp';
  await writeFile(temporary, bytes);
  await rename(temporary, destination);
}

// Keep source artwork for editing; ship only assets referenced by the application.
const applicationFiles = (await listFiles(source)).filter((name) => !name.startsWith('assets/'));
const files = new Map();
const assets = new Set();
for (const name of applicationFiles) {
  const bytes = await readFile(resolve(source, name));
  files.set(name, bytes);
  for (const match of bytes.toString('utf8').matchAll(/assets\/[A-Za-z0-9_./-]+/g))
    assets.add(match[0]);
}
for (const name of assets) {
  const path = resolve(source, name);
  if (!path.startsWith(resolve(source, 'assets') + sep)) throw new Error(`Invalid asset: ${name}`);
  files.set(name, await readFile(path));
}

await mkdir(output, { recursive: true });
// Publish dependencies first; the entry points and version marker are written last.
const names = [...files.keys()].sort(
  (a, b) =>
    Number(['app.js', 'index.html'].includes(a)) - Number(['app.js', 'index.html'].includes(b)) ||
    a.localeCompare(b),
);
for (const name of names) await writeChangedFile(name, files.get(name));
for (const name of await listFiles(output)) {
  if (name !== 'app-version.json' && !files.has(name)) await rm(outputPath(name), { force: true });
}
await writeChangedFile('app-version.json', Buffer.from(JSON.stringify({ buildId: Date.now() })));

const size = [...files.values()].reduce((sum, bytes) => sum + bytes.length, 0);
console.log(
  `Frontend built: ${relative(project, output)}; ${assets.size} assets; ${(size / 1024 / 1024).toFixed(2)} MiB`,
);
