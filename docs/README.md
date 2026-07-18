# Documentation index

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

**One MCP — four ship modes** (switches, not separate packages):

| Mode | Guide | Wrapper |
|------|--------|---------|
| **A** Local host | [`local-ngrok/`](local-ngrok/) | `./scripts/run.sh --mode http` |
| **B** Docker / Podman | [`PUBLISH-MODES.md`](PUBLISH-MODES.md)#b--docker--podman | `./scripts/run.sh --mode podman` |
| **C** Code Engine | [`code-engine/`](code-engine/) | `./scripts/run.sh --mode ce` |
| **D** Cursor / VS Code IDE | [`ide/`](ide/) · [`PUBLISH-MODES.md`](PUBLISH-MODES.md)#d--vs-code--cursor-ide-mcp | `./scripts/run.sh --mode ide` |

Full matrix: **[PUBLISH-MODES.md](PUBLISH-MODES.md)**

Shared:

- **[WHY-THIS-MCP.md](WHY-THIS-MCP.md)** — how this gateway lifts WxO Slack limitations (with tags)  
- [SETUP.md](../SETUP.md) — Slack scopes, WxO agents, env overview  
- [IDE setup](ide/) — Cursor, VS Code, IBM Bob, Antigravity, Claude Desktop  
- [Frameworks](frameworks/) — LangGraph, LlamaIndex, OpenAI Agents (connect *to* MCP)  
- [examples/mcp/](../examples/mcp/) — copy-paste `mcp.json` templates  
- [USE_CASES.md](../USE_CASES.md) — real-world scenarios  
- [config.example.yaml](../config.example.yaml) · [.env.example](../.env.example)  
- Example agents: [`agent.yaml`](../agent.yaml), [`agents/`](../agents/)
