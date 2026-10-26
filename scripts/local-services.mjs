import { spawn } from "node:child_process";
import { resolve } from "node:path";

const workspaceKey = (value) => {
  const normalized = resolve(value).replaceAll("\\", "/").replace(/\/$/, "");
  return process.platform === "win32" ? normalized.toLowerCase() : normalized;
};

export async function probeService(url, kind, workspace) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1500);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) return "foreign";
    if (kind === "api") {
      const identity = await response.json();
      return identity.app === "slimeops" &&
        (!workspace ||
          (typeof identity.workspace === "string" &&
            workspaceKey(identity.workspace) === workspaceKey(workspace)))
        ? "ready"
        : "foreign";
    }
    if (workspace) {
      const reported = response.headers.get("X-SlimeOps-Workspace");
      if (
        !reported ||
        workspaceKey(decodeURIComponent(reported)) !== workspaceKey(workspace)
      )
        return "foreign";
    }
    const html = await response.text();
    return html.includes("SlimeOps") && html.includes('id="slimeRoom"')
      ? "ready"
      : "foreign";
  } catch (error) {
    return error.cause?.code === "ECONNREFUSED" ? "missing" : "foreign";
  } finally {
    clearTimeout(timer);
  }
}

export async function waitForService(
  url,
  kind,
  { timeout = 15000, stopped = () => false, workspace } = {},
) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline && !stopped()) {
    if ((await probeService(url, kind, workspace)) === "ready") return;
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  throw new Error(
    stopped() ? "Arranque cancelado." : `No se pudo iniciar ${kind}: ${url}`,
  );
}

export function spawnLocal(command, args, options = {}) {
  return spawn(command, args, {
    stdio: "inherit",
    windowsHide: true,
    ...options,
  });
}

export async function stopChild(child) {
  if (!child?.pid || child.exitCode !== null || child.signalCode !== null)
    return;
  if (process.platform === "win32") {
    const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      windowsHide: true,
    });
    const code = await new Promise((resolve) => {
      killer.once("exit", resolve);
      killer.once("error", () => resolve(1));
    });
    if (code !== 0 && child.exitCode === null && child.signalCode === null)
      child.kill();
  } else {
    child.kill("SIGTERM");
    await Promise.race([
      new Promise((resolve) => child.once("exit", resolve)),
      new Promise((resolve) => setTimeout(resolve, 2000)),
    ]);
    if (child.exitCode === null && child.signalCode === null)
      child.kill("SIGKILL");
  }
}

export function openBrowser(url) {
  const [command, args] =
    process.platform === "win32"
      ? ["cmd.exe", ["/c", "start", "", url]]
      : process.platform === "darwin"
        ? ["open", [url]]
        : ["xdg-open", [url]];
  const opener = spawn(command, args, {
    stdio: "ignore",
    detached: true,
    windowsHide: true,
  });
  opener.on("error", (error) => console.error(`Abre ${url}: ${error.message}`));
  opener.unref();
}
