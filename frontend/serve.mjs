import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { spawn } from 'node:child_process';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendDirectory = fileURLToPath(new URL('.', import.meta.url));
const distDirectory = resolve(frontendDirectory, '../dist');
const host = '127.0.0.1';
const port = Number(process.env.PORT || 4173);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error('PORT debe ser un entero entre 1 y 65535');
}
const url = `http://${host}:${port}`;
const mimeTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.woff2': 'font/woff2',
};

const server = createServer(async (request, response) => {
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    response.writeHead(405, { Allow: 'GET, HEAD' }).end('Method not allowed');
    return;
  }

  let pathname;
  try {
    pathname = decodeURIComponent(new URL(request.url, `http://${host}`).pathname);
  } catch {
    response.writeHead(400).end('Bad request');
    return;
  }

  const relativePath = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const filePath = resolve(distDirectory, relativePath);
  if (filePath !== distDirectory && !filePath.startsWith(`${distDirectory}${sep}`)) {
    response.writeHead(403).end('Forbidden');
    return;
  }

  try {
    const fileInfo = await stat(filePath);
    if (!fileInfo.isFile()) throw new Error('Not a file');
    response.writeHead(200, {
      'Content-Length': fileInfo.size,
      'Content-Type': mimeTypes[extname(filePath).toLowerCase()] || 'application/octet-stream',
      'X-SlimeOps-Workspace': encodeURIComponent(resolve(frontendDirectory, '..')),
    });
    if (request.method === 'HEAD') response.end();
    else createReadStream(filePath).pipe(response);
  } catch {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Not found');
  }
});

server.listen(port, host, () => {
  console.log(`Frontend disponible en ${url}`);
  console.log('Pulsa Ctrl+C para detenerlo.');
  if (process.env.SLIMEOPS_NO_BROWSER === '1') return;
  const opener =
    process.platform === 'win32'
      ? spawn('cmd.exe', ['/c', 'start', '', url], {
          detached: true,
          stdio: 'ignore',
          windowsHide: true,
        })
      : process.platform === 'darwin'
        ? spawn('open', [url], { detached: true, stdio: 'ignore' })
        : spawn('xdg-open', [url], { detached: true, stdio: 'ignore' });
  opener.on('error', (error) => console.error(`No se pudo abrir el navegador: ${error.message}`));
  opener.unref();
});
