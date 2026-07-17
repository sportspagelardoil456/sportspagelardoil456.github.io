# Publish — npm + GitHub

**Package:** [`@markusvankempen/slack-wxo-mcp-gateway`](https://www.npmjs.com/package/@markusvankempen/slack-wxo-mcp-gateway)  
**Source / docs:** [https://github.com/markusvankempen/slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway)  
**Author:** [Markus van Kempen](https://github.com/markusvankempen)

All npm and MCP package metadata must point at `https://github.com/markusvankempen` (see `package.json` `repository`, `homepage`, `bugs`, `author.url`, and `mcpName`).

---

## 1. Sync public repo (docs + package source)

From this directory (or via the sync script):

```bash
./scripts/sync-public-repo.sh
```

Or manually:

```bash
gh auth switch --user markusvankempen
gh repo create markusvankempen/slack-wxo-mcp-gateway \
  --public \
  --description "Slack ↔ watsonx Orchestrate MCP gateway (streamable HTTP)" \
  --source /tmp/slack-wxo-mcp-gateway-publish \
  --remote origin \
  --push
```

Never push `.env`, `config.yaml`, or `.run/` (secrets / local state).

---

## 2. Publish to npm

```bash
npm login   # as markusvankempen (or org with publish rights)
npm version patch   # when bumping
npm publish --access public
```

Verify:

```bash
npm view @markusvankempen/slack-wxo-mcp-gateway
npx @markusvankempen/slack-wxo-mcp-gateway
```

---

## 3. MCP registry name

`package.json` includes:

```json
"mcpName": "io.github.markusvankempen/slack-wxo-mcp-gateway"
```

This follows the `io.github.<user>/<package>` convention used by other Markus packages (e.g. code-engine-mcp-server).

---

## 4. Consumers

| Client | How |
|--------|-----|
| Local host | `npx @markusvankempen/slack-wxo-mcp-gateway` (needs Python 3.10+) |
| watsonx Orchestrate | `orchestrate toolkits add -k mcp … --url https://YOUR_HOST/mcp --transport streamable_http` |
| Cursor / Claude | Remote MCP URL `https://YOUR_HOST/mcp` (streamable HTTP) |

Docs live only on the GitHub repo above — keep README + USE_CASES in sync before each release.
