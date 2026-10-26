import { spawn } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const python = resolve(
  root,
  'backend/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
);
const commands = [
  [python, ['-m', 'unittest', 'discover', '-s', 'tests'], resolve(root, 'backend')],
  [
    process.execPath,
    [
      '--preserve-symlinks',
      '--preserve-symlinks-main',
      '--experimental-vm-modules',
      '--test',
      'tests',
    ],
    resolve(root, 'frontend'),
  ],
];
for (const [command, args, cwd] of commands) {
  const child = spawn(command, args, { cwd, stdio: 'inherit', windowsHide: true });
  const code = await new Promise((resolve) => {
    child.once('exit', resolve);
    child.once('error', (error) => {
      console.error(error.message);
      resolve(1);
    });
  });
  if (code !== 0) {
    process.exitCode = code || 1;
    break;
  }
}
