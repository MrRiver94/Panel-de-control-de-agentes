import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import {
  probeService,
  waitForService,
  spawnLocal,
  stopChild,
  openBrowser,
} from "./local-services.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const api = "http://127.0.0.1:8000";
const front = "http://127.0.0.1:4173";
const python = resolve(
  root,
  "backend/.venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const children = [];
let closing = false,
  ownsApi = false,
  heartbeat;
let finish;
const stopped = new Promise((resolve) => {
  finish = resolve;
});

async function cancelOwnedMission() {
  if (!ownsApi) return;
  const options = {
    headers: { "X-Operator-Id": "super-admin" },
    signal: AbortSignal.timeout(2000),
  };
  try {
    const executions = await (
      await fetch(api + "/api/executions?summary=true", options)
    ).json();
    const active = executions.filter((item) =>
      ["queued", "running", "cancelling"].includes(item.status),
    );
    for (const execution of active)
      await fetch(`${api}/api/executions/${execution.id}/cancel`, {
        ...options,
        method: "POST",
      });
    const deadline = Date.now() + 5000;
    while (active.length && Date.now() < deadline) {
      const current = await (
        await fetch(api + "/api/executions?summary=true", {
          ...options,
          signal: AbortSignal.timeout(1500),
        })
      ).json();
      if (
        !current.some((item) =>
          ["queued", "running", "cancelling"].includes(item.status),
        )
      )
        break;
      await new Promise((resolve) => setTimeout(resolve, 150));
    }
  } catch {
    /* The API's process lifetime guard also closes its Codex children. */
  }
}

async function stop(code = 0) {
  if (closing) return stopped;
  closing = true;
  clearInterval(heartbeat);
  await cancelOwnedMission();
  for (const child of [...children].reverse()) await stopChild(child);
  process.exitCode = code;
  finish();
}

function launch(command, args, options = {}) {
  const child = spawnLocal(command, args, { cwd: root, ...options });
  children.push(child);
  child.once("error", (error) => {
    console.error(error.message);
    void stop(1);
  });
  return child;
}

process.once("SIGINT", () => {
  void stop();
});
process.once("SIGTERM", () => {
  void stop();
});

try {
  const apiState = await probeService(api + "/health", "api", root);
  if (apiState === "foreign")
    throw new Error(
      "El puerto 8000 está ocupado por otro servicio o una API antigua. Cierra esa instancia y vuelve a ejecutar npm start.",
    );
  if (apiState === "missing" && !existsSync(python))
    throw new Error(
      "Falta backend/.venv. Desde backend: python -m venv .venv; después instala requirements.txt con su Python.",
    );
  const builder = launch(process.execPath, [
    "--preserve-symlinks-main",
    resolve(root, "frontend/build.mjs"),
  ]);
  const buildCode = await new Promise((resolve) => {
    builder.once("exit", resolve);
    builder.once("error", () => resolve(1));
  });
  if (buildCode !== 0 && !closing)
    throw new Error("La compilación del frontend ha fallado.");
  if (!closing && apiState === "missing") {
    const child = launch(
      python,
      [
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
        "--no-access-log",
      ],
      {
        cwd: resolve(root, "backend"),
        env: { ...process.env, SLIMEOPS_MONITOR_ONLY: process.env.SLIMEOPS_MONITOR_ONLY || "1" },
      },
    );
    ownsApi = true;
    child.once("exit", (code) => {
      if (!closing) {
        console.error(`La API se cerró (${code}).`);
        void stop(1);
      }
    });
    await waitForService(api + "/health", "api", {
      stopped: () => closing,
      workspace: root,
    });
  } else if (!closing) console.log("API de SlimeOps ya abierta; se reutiliza.");
  if (!closing) {
    const frontState = await probeService(front, "front", root);
    if (frontState === "foreign")
      throw new Error("El puerto 4173 está ocupado por otro servicio.");
    if (frontState === "missing") {
      const child = launch(process.execPath, [
        "--preserve-symlinks-main",
        resolve(root, "frontend/serve.mjs"),
      ]);
      child.once("exit", (code) => {
        if (!closing) {
          console.error(`El frontend se cerró (${code}).`);
          void stop(1);
        }
      });
      await waitForService(front, "front", {
        stopped: () => closing,
        workspace: root,
      });
    } else {
      console.log("Frontend de SlimeOps ya abierto; se reutiliza.");
      if (process.env.SLIMEOPS_NO_BROWSER !== "1") openBrowser(front);
    }
    console.log(
      `SlimeOps disponible en ${front}\nCtrl+C cierra los procesos iniciados desde esta terminal.`,
    );
    heartbeat = setInterval(() => {}, 60000);
    await stopped;
  }
} catch (error) {
  if (!closing) {
    console.error(error.message);
    await stop(1);
  }
}
