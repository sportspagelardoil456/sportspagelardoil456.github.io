#!/usr/bin/env node
/**
 * Author: Markus van Kempen
 * Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
 * Web: https://markusvankempen.github.io/
 */
"use strict";

const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const PKG_ROOT = path.resolve(__dirname, "..");
const PARENT = path.resolve(PKG_ROOT, "..");

function findPython() {
  for (const cmd of ["python3", "python"]) {
    const r = spawnSync(cmd, ["--version"], { encoding: "utf8" });
    if (r.status === 0) return cmd;
  }
  return null;
}

function ensureDeps(python) {
  if (process.env.SLACK_WXO_SKIP_PIP === "1") return;
  const marker = path.join(PKG_ROOT, ".deps-ok");
  if (fs.existsSync(marker)) return;
  const req = path.join(PKG_ROOT, "requirements.txt");
  if (!fs.existsSync(req)) return;
  console.error("[slack-wxo-mcp-gateway] Installing Python deps (first run)…");
  const r = spawnSync(python, ["-m", "pip", "install", "-q", "-r", req], {
    stdio: "inherit",
    env: process.env,
  });
  if (r.status !== 0) {
    console.error(
      `[slack-wxo-mcp-gateway] pip install failed. Run:\n  ${python} -m pip install -r ${req}\n` +
        "Docs: https://github.com/markusvankempen/slack-wxo-mcp-gateway"
    );
    process.exit(r.status || 1);
  }
  try {
    fs.writeFileSync(marker, new Date().toISOString());
  } catch {
    /* ignore */
  }
}

function main() {
  const python = findPython();
  if (!python) {
    console.error(
      "[slack-wxo-mcp-gateway] Python 3.10+ is required.\n" +
        "Docs: https://github.com/markusvankempen/slack-wxo-mcp-gateway"
    );
    process.exit(1);
  }

  ensureDeps(python);

  const cliArgs = process.argv.slice(2);
  const wantStdio =
    cliArgs.includes("--stdio") ||
    (process.env.GATEWAY_TRANSPORT || "").toLowerCase() === "stdio";

  const env = {
    ...process.env,
    GATEWAY_HOST: process.env.GATEWAY_HOST || "0.0.0.0",
    GATEWAY_PORT: process.env.GATEWAY_PORT || process.env.PORT || "3100",
  };
  // Cursor / VS Code / Bob / Antigravity launch via stdio by default when --stdio is passed
  // or GATEWAY_TRANSPORT=stdio is set in mcp.json env.
  if (wantStdio) {
    env.GATEWAY_TRANSPORT = "stdio";
  }

  let args;
  if (path.basename(PKG_ROOT) === "slack_mcp_gateway") {
    env.PYTHONPATH = [PARENT, process.env.PYTHONPATH || ""]
      .filter(Boolean)
      .join(path.delimiter);
    args = ["-m", "slack_mcp_gateway", ...cliArgs];
  } else {
    // npm layout: package root is not named slack_mcp_gateway
    const pyArgv = JSON.stringify(["slack_mcp_gateway", ...cliArgs]);
    args = [
      "-c",
      [
        "import sys, types",
        `root = r'''${PKG_ROOT}'''`,
        "sys.path.insert(0, root)",
        `sys.argv = ${pyArgv}`,
        "pkg = types.ModuleType('slack_mcp_gateway')",
        "pkg.__path__ = [root]",
        "sys.modules['slack_mcp_gateway'] = pkg",
        "from slack_mcp_gateway.server import main",
        "main()",
      ].join("; "),
    ];
  }

  const child = spawn(python, args, { stdio: "inherit", env });
  child.on("exit", (code, signal) => {
    if (signal) process.kill(process.pid, signal);
    process.exit(code == null ? 1 : code);
  });
}

main();
