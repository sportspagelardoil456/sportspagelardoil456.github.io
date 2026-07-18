# Publish — docs (public) · source (private) · npm

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

| Surface | What’s published | URL |
|---------|------------------|-----|
| GitHub **public** | Docs + metadata only (no app source) | [slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway) |
| GitHub **private** | Full application source + docs | [slack-wxo-mcp-gateway-dev](https://github.com/markusvankempen/slack-wxo-mcp-gateway-dev) |
| npm | Installable package | [`@markusvankempen/slack-wxo-mcp-gateway`](https://www.npmjs.com/package/@markusvankempen/slack-wxo-mcp-gateway) |
| MCP Registry | `server.json` manifest | `io.github.markusvankempen/slack-wxo-mcp-gateway` |
| Site | Agentic AI Bridge | [https://markusvankempen.github.io/](https://markusvankempen.github.io/) |

**Public GitHub must never contain** `*.py`, `bin/`, `ui.html`, `Dockerfile`, `requirements.txt`, or deploy/run scripts.

---

## 1. Sync GitHub

```bash
gh auth switch --user markusvankempen
./scripts/sync-public-repo.sh    # docs only
./scripts/sync-private-repo.sh   # full source
```

Never push `.env`, `config.yaml`, `.run/`, `.mcpregistry*`, or secrets.

---

## 2. Publish npm + MCP Registry (from private / local full tree)

```bash
npm login
npm publish --access public --otp=XXXXXX
mcp-publisher login github
mcp-publisher publish
```

Bump `package.json` + `server.json` `version` before each publish.

---

## 3. Consumers

| Client | How |
|--------|-----|
| Install | `npx -y @markusvankempen/slack-wxo-mcp-gateway` |
| watsonx Orchestrate | Toolkit URL `https://YOUR_HOST/mcp` (`streamable_http`) |
| IDE stdio | `npx -y @markusvankempen/slack-wxo-mcp-gateway --stdio` |
