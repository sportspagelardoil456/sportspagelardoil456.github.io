# Publish & run modes — one MCP, four ways to ship

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

`tags:` `npm` · `npx` · `docker` · `podman` · `code-engine` · `cursor` · `vscode` · `stdio` · `streamable-http`

**One package / one image.** Modes are switches — not separate MCP servers.

| Mode | Switch | What you get |
|------|--------|----------------|
| **A** Local host | `./scripts/run.sh --mode http` | Gateway on `:3100` — UI + `/mcp` + poller |
| **B** Docker / Podman | `./scripts/run.sh --mode podman` | Same app in a container on `:8080` |
| **C** Code Engine | `./scripts/run.sh --mode ce` | Always-on HTTPS + secrets |
| **D** IDE MCP | `./scripts/run.sh --mode ide` | Cursor / VS Code **stdio** (or remote to A/B/C) |

Optional demo tunnel: `--mode ngrok` (local HTTP + ngrok + WxO toolkit register).

Wrapper: [`scripts/run.sh`](../scripts/run.sh)

```text
  @markusvankempen/slack-wxo-mcp-gateway   (npm)
  + Dockerfile                             (one image)
           │
           ├─ A http / ngrok
           ├─ B podman|docker
           ├─ C code-engine
           └─ D ide (stdio) ──► Cursor / VS Code / Bob / …
```

---

## Shared switches

| Env / flag | Meaning |
|------------|---------|
| `GATEWAY_TRANSPORT=streamable-http` | Default for A/B/C — `/mcp` |
| `GATEWAY_TRANSPORT=stdio` or `--stdio` | Mode **D** — IDE local MCP |
| `GATEWAY_ENABLE_POLLER=0\|1` | Poller (off by default in stdio) |
| `PORT` / `GATEWAY_PORT` | Listen port (CE uses `PORT`) |
| `GATEWAY_ADMIN_USER` / `PASSWORD` | Lock admin UI on public hosts |

Artifacts to publish once (same semver):

1. **npm** `@markusvankempen/slack-wxo-mcp-gateway`  
2. **Container image** (optional GHCR/ICR tag `1.0.0`)  
3. **Docs** (this repo)

---

## A — Standalone local host

```bash
cp .env.example .env && cp config.example.yaml config.yaml
./scripts/run.sh --mode http
# → http://127.0.0.1:3100/  and  /mcp
```

Or: `npx @markusvankempen/slack-wxo-mcp-gateway`  
Public WxO/Slack Events: [`local-ngrok/`](local-ngrok/) or `--mode ngrok`.

---

## B — Docker / Podman

```bash
./scripts/run.sh --mode podman          # or --mode docker
# IMAGE=slack-wxo-gateway:local  PORT=8080
```

Manual:

```bash
podman build -t slack-wxo-gateway:local .
podman run --rm -p 8080:8080 --env-file .env \
  -e PORT=8080 -e GATEWAY_REQUIRE_AUTH=true \
  slack-wxo-gateway:local
```

Persist config (optional): `-v "$PWD/config.yaml:/tmp/slack_mcp_gateway_config.yaml"`.

---

## C — IBM Code Engine

```bash
./scripts/run.sh --mode ce
# wraps ./deploy_code_engine.sh
```

Details: [`code-engine/`](code-engine/).  
WxO: `--url https://YOUR-CE-APP/mcp --transport streamable_http`.

Same **Dockerfile** as B — CE can source-build or pull a prebuilt image.

---

## D — VS Code / Cursor IDE MCP

### D1 — Local stdio (tools in the IDE)

```bash
./scripts/run.sh --mode ide
# prints mcp.json snippets + can exec stdio server
```

**Cursor** → `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "slack-wxo-gateway": {
      "command": "npx",
      "args": ["-y", "@markusvankempen/slack-wxo-mcp-gateway", "--stdio"],
      "env": {
        "GATEWAY_TRANSPORT": "stdio",
        "SLACK_BOT_TOKEN": "xoxb-…",
        "WXO_INSTANCE_URL": "https://…",
        "WXO_API_KEY": "…"
      }
    }
  }
}
```

**VS Code** → User `mcp.json` / `.vscode/mcp.json`:

```json
{
  "servers": {
    "slack-wxo-gateway": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@markusvankempen/slack-wxo-mcp-gateway", "--stdio"],
      "env": {
        "GATEWAY_TRANSPORT": "stdio",
        "SLACK_BOT_TOKEN": "xoxb-…",
        "WXO_INSTANCE_URL": "https://…",
        "WXO_API_KEY": "…"
      }
    }
  }
}
```

Templates: [`examples/mcp/cursor-local.json`](../examples/mcp/cursor-local.json) · [`vscode-local.json`](../examples/mcp/vscode-local.json)  
Guides: [`ide/cursor.md`](ide/cursor.md) · [`ide/vscode.md`](ide/vscode.md)

### D2 — IDE → remote gateway (A/B/C already running)

Point the IDE at the hosted `/mcp` (poller + UI stay on the host):

```json
{
  "mcpServers": {
    "slack-wxo-gateway": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://YOUR_HOST/mcp"]
    }
  }
}
```

VS Code native HTTP: `{ "type": "http", "url": "https://YOUR_HOST/mcp" }`.

---

## Which mode when?

| Goal | Mode |
|------|------|
| Hack on tools in Cursor/VS Code only | **D1** stdio |
| Full Slack poller + admin UI on laptop | **A** (+ **ngrok** for WxO) |
| Same as A but containerized | **B** |
| Production / stable Slack Events + WxO | **C** |
| IDE tools against prod gateway | **D2** → C’s `/mcp` |

---

## Version alignment

Tag npm and image together:

```bash
npm version 1.0.0
podman build -t ghcr.io/markusvankempen/slack-wxo-mcp-gateway:1.0.0 .
```

Do **not** publish separate npm names per mode.
