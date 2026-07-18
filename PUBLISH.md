# Publish — npm + MCP Registry + GitHub

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

| Surface | URL |
|---------|-----|
| npm | [`@markusvankempen/slack-wxo-mcp-gateway`](https://www.npmjs.com/package/@markusvankempen/slack-wxo-mcp-gateway) |
| MCP Registry | `io.github.markusvankempen/slack-wxo-mcp-gateway` |
| GitHub (source + docs) | [slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway) |
| GitHub (private mirror) | [slack-wxo-mcp-gateway-dev](https://github.com/markusvankempen/slack-wxo-mcp-gateway-dev) |
| Site | [https://markusvankempen.github.io/](https://markusvankempen.github.io/) |

**Run modes A–D:** [`docs/PUBLISH-MODES.md`](docs/PUBLISH-MODES.md) · `./scripts/run.sh --mode http|podman|ce|ide`

---

## 1. Sync to GitHub

Public repo = **full npm package** (Python source, `bin/`, docs, `server.json`).

```bash
gh auth switch --user markusvankempen
./scripts/sync-public-repo.sh
./scripts/sync-private-repo.sh   # optional private mirror
```

Never push `.env`, `config.yaml`, `.run/`, `.mcpregistry*`, or secrets.

---

## 2. Publish npm + MCP Registry

```bash
npm login
npm publish --access public --otp=XXXXXX
mcp-publisher login github
mcp-publisher publish
```

Bump `package.json` + `server.json` `version` before each publish (npm versions are immutable).

| Field | Value |
|-------|--------|
| `name` | `@markusvankempen/slack-wxo-mcp-gateway` |
| `mcpName` | `io.github.markusvankempen/slack-wxo-mcp-gateway` |
| `homepage` / `websiteUrl` | `https://markusvankempen.github.io/` |
| `repository` | `https://github.com/markusvankempen/slack-wxo-mcp-gateway.git` |

---

## 3. Consumers

| Client | How |
|--------|-----|
| watsonx Orchestrate | Toolkit URL `https://YOUR_HOST/mcp` (`streamable_http`) |
| Cursor / Claude | Remote `/mcp` or `npx -y mcp-remote …` |
| Local / IDE stdio | `npx -y @markusvankempen/slack-wxo-mcp-gateway --stdio` |
