# Publish — GitHub docs + npm (later)

**Docs (this repo):** [https://github.com/markusvankempen/slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway)  
**npm (planned):** [`@markusvankempen/slack-wxo-mcp-gateway`](https://www.npmjs.com/package/@markusvankempen/slack-wxo-mcp-gateway)  
**Author:** [Markus van Kempen](https://github.com/markusvankempen)

This GitHub repository is **documentation only** for now (no application source).  
All npm / MCP package references should still point at `https://github.com/markusvankempen`.

---

## 1. Sync docs to GitHub

From the private project tree:

```bash
./scripts/sync-public-repo.sh
```

Pushes only:

- `README.md`
- `USE_CASES.md`
- `PUBLISH.md`
- `LICENSE`
- `config.example.yaml`
- `.env.example`

Never push `.env`, `config.yaml`, `.run/`, or source code.

---

## 2. Publish to npm (when ready)

Application source stays private until you choose to open it. When publishing:

```bash
npm login   # as markusvankempen
npm publish --access public
```

Package metadata (local `package.json`) must keep:

| Field | Value |
|-------|--------|
| `name` | `@markusvankempen/slack-wxo-mcp-gateway` |
| `repository.url` | `https://github.com/markusvankempen/slack-wxo-mcp-gateway.git` |
| `homepage` | `https://github.com/markusvankempen/slack-wxo-mcp-gateway#readme` |
| `bugs.url` | `https://github.com/markusvankempen/slack-wxo-mcp-gateway/issues` |
| `mcpName` | `io.github.markusvankempen/slack-wxo-mcp-gateway` |
| `author.url` | `https://github.com/markusvankempen` |

---

## 3. Consumers (hosted MCP)

| Client | How |
|--------|-----|
| watsonx Orchestrate | `orchestrate toolkits add -k mcp … --url https://YOUR_HOST/mcp --transport streamable_http` |
| Cursor / Claude | Remote MCP URL `https://YOUR_HOST/mcp` (streamable HTTP) |
| Local (later) | `npx @markusvankempen/slack-wxo-mcp-gateway` after npm publish |

Keep README + USE_CASES in sync before each docs push.
