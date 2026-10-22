import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const source = resolve("frontend/src");
const output = resolve("dist");
await rm(output, { recursive: true, force: true });
await mkdir(output, { recursive: true });
await cp(source, output, { recursive: true });
await writeFile(resolve(output, "app-version.json"), JSON.stringify({ buildId: Date.now() }));
console.log(`Frontend built: ${output}`);
