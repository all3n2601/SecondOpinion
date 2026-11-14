#!/usr/bin/env node
// Run the project's virtual-environment Python with the given arguments, on Windows, macOS or Linux.
// The npm scripts call this instead of `.venv/bin/python`, which does not exist on Windows
// (there it is `.venv\Scripts\python.exe`).
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const candidates =
  process.platform === "win32"
    ? [join(root, ".venv", "Scripts", "python.exe")]
    : [join(root, ".venv", "bin", "python"), join(root, ".venv", "bin", "python3")];
const python = candidates.find((path) => existsSync(path));

if (!python) {
  const create =
    process.platform === "win32"
      ? "py -3.13 -m venv .venv; .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
      : "python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt";
  console.error(`No Python virtual environment found at ${join(root, ".venv")}.`);
  console.error(`Create it from the repository root first:\n  ${create}`);
  process.exit(1);
}

const child = spawn(python, process.argv.slice(2), {
  cwd: root,
  stdio: "inherit",
  // unseal.py and our CLI print check marks; a Windows console needs UTF-8 to print them.
  env: { PYTHONUTF8: "1", ...process.env },
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}
child.on("error", (error) => {
  console.error(`Could not start ${python}: ${error.message}`);
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
