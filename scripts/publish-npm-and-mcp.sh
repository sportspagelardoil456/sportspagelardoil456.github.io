#!/usr/bin/env bash
# ---
# Author: Markus van Kempen
# Email: mvankempen@ca.ibm.com | markus.van.kempen@gmail.com
# Web: https://markusvankempen.github.io/
# ---
# Publish to npm then MCP Registry (mcp-publisher).
# Prereqs:
#   npm login          # as markusvankempen (scope owner)
#   mcp-publisher login github
#   gh auth switch --user markusvankempen
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Sync docs (includes server.json) to GitHub…"
bash "$ROOT/scripts/sync-public-repo.sh" || true

echo "==> npm whoami…"
if ! npm whoami >/dev/null 2>&1; then
  echo "ERROR: npm not authenticated. Run: npm login" >&2
  exit 1
fi
echo "    logged in as $(npm whoami)"

VER="$(node -p "require('./package.json').version")"
MCP_NAME="$(node -p "require('./package.json').mcpName")"
echo "==> version=$VER mcpName=$MCP_NAME"

# Keep server.json versions in sync
node -e "
const fs=require('fs');
const pkg=JSON.parse(fs.readFileSync('package.json','utf8'));
const s=JSON.parse(fs.readFileSync('server.json','utf8'));
s.version=pkg.version;
if(s.packages&&s.packages[0]) s.packages[0].version=pkg.version;
fs.writeFileSync('server.json', JSON.stringify(s,null,2)+'\n');
console.log('server.json version →', pkg.version);
"

echo "==> npm publish --access public…"
npm publish --access public

echo "==> mcp-publisher publish…"
mcp-publisher publish

echo ""
echo "============================================================"
echo " PUBLISHED"
echo "  npm : https://www.npmjs.com/package/@markusvankempen/slack-wxo-mcp-gateway"
echo "  MCP : https://registry.modelcontextprotocol.io/servers/${MCP_NAME//\//%2F}"
echo "============================================================"
