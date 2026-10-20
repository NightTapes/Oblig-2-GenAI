// Next's standalone server needs static assets copied next to its generated bundle.
import { cp, access } from "node:fs/promises";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
const root = fileURLToPath(new URL("..", import.meta.url));
const standalone = path.join(root, ".next/standalone");
await cp(
  path.join(root, ".next/static"),
  path.join(standalone, ".next/static"),
  { recursive: true },
);
try {
  await access(path.join(root, "public"));
  await cp(path.join(root, "public"), path.join(standalone, "public"), {
    recursive: true,
  });
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
const portFlag = process.argv.indexOf("--port");
const server = spawn(process.execPath, [path.join(standalone, "server.js")], {
  stdio: "inherit",
  env: {
    ...process.env,
    HOSTNAME: "0.0.0.0",
    PORT:
      portFlag >= 0 ? process.argv[portFlag + 1] : process.env.PORT || "3000",
  },
});
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => server.kill(signal));
server.on("exit", (code) => process.exit(code ?? 0));
server.on("error", (error) => {
  console.error(error.message);
  process.exit(1);
});
