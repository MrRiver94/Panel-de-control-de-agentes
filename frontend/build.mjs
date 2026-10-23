import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendDirectory = dirname(fileURLToPath(import.meta.url));
const source = resolve(frontendDirectory, "src");
const output = resolve(frontendDirectory, "../dist");
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(source, output, { recursive: true });
await writeFile(resolve(output, "app-version.json"), JSON.stringify({ buildId: Date.now() }));
console.log(`Frontend built: ${output}`);
