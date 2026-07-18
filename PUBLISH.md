# Publish — GitHub docs + npm (later)

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

This GitHub repository is **documentation only** for now (no application source).  
All npm / MCP package references should still point at `https://github.com/markusvankempen`.

**Run modes A–D** (one package, switches — not four MCP servers):  
[`docs/PUBLISH-MODES.md`](docs/PUBLISH-MODES.md) · `./scripts/run.sh --mode http|podman|ce|ide`

| Mode | Command |
|------|---------|
| A Local HTTP | `./scripts/run.sh --mode http` |
| B Podman/Docker | `./scripts/run.sh --mode podman` |
| C Code Engine | `./scripts/run.sh --mode ce` |
| D Cursor/VS Code IDE | `./scripts/run.sh --mode ide` |

---

## 1. Sync docs to GitHub

From the private project tree:

```bash
./scripts/sync-public-repo.sh
```

Never push `.env`, `config.yaml`, `.run/`, or application source.

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
