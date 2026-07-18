# Publish — npm + MCP Registry + GitHub docs

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

| Surface | URL |
|---------|-----|
| npm | [`@markusvankempen/slack-wxo-mcp-gateway`](https://www.npmjs.com/package/@markusvankempen/slack-wxo-mcp-gateway) |
| MCP Registry | `io.github.markusvankempen/slack-wxo-mcp-gateway` |
| GitHub docs (public) | [slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway) |
| GitHub code+docs (private) | [slack-wxo-mcp-gateway-dev](https://github.com/markusvankempen/slack-wxo-mcp-gateway-dev) |

**Run modes A–D** (one package, switches — not four MCP servers):  
[`docs/PUBLISH-MODES.md`](docs/PUBLISH-MODES.md) · `./scripts/run.sh --mode http|podman|ce|ide`

| Mode | Command |
|------|---------|
| A Local HTTP | `./scripts/run.sh --mode http` |
| B Podman/Docker | `./scripts/run.sh --mode podman` |
| C Code Engine | `./scripts/run.sh --mode ce` |
| D Cursor/VS Code IDE | `./scripts/run.sh --mode ide` |

---

## 1. Sync to GitHub

```bash
gh auth switch --user markusvankempen

# Public docs-only
./scripts/sync-public-repo.sh

# Private full source + docs
./scripts/sync-private-repo.sh
```

Never push `.env`, `config.yaml`, `.run/`, `.mcpregistry*`, or other secrets.

---

## 2. Publish to npm + MCP Registry

Order matters: **npm first** (package must exist), then **mcp-publisher**.

```bash
npm login                                    # as markusvankempen
npm publish --access public --otp=XXXXXX     # 2FA required
mcp-publisher login github                   # or: -token "$(gh auth token)"
mcp-publisher publish                        # reads server.json
```

One-shot helper (after `npm login` / OTP):

```bash
./scripts/publish-npm-and-mcp.sh
# or with OTP:
npm publish --access public --otp=XXXXXX && mcp-publisher publish
```

| Field | Value |
|-------|--------|
| `name` | `@markusvankempen/slack-wxo-mcp-gateway` |
| `mcpName` | `io.github.markusvankempen/slack-wxo-mcp-gateway` |
| `server.json` | Registry manifest (`runtimeHint: npx`, `--stdio`) |
| `homepage` / `websiteUrl` | `https://markusvankempen.github.io/` |
| `repository.url` | `https://github.com/markusvankempen/slack-wxo-mcp-gateway.git` |

---

## 3. Consumers (hosted MCP)

| Client | How |
|--------|-----|
| watsonx Orchestrate | `orchestrate toolkits add -k mcp … --url https://YOUR_HOST/mcp --transport streamable_http` |
| Cursor / Claude | Remote MCP URL `https://YOUR_HOST/mcp` (streamable HTTP) |
| Local (later) | `npx @markusvankempen/slack-wxo-mcp-gateway` after npm publish |

Keep README + USE_CASES in sync before each docs push.
