# Documentation index

**Repo:** [https://github.com/markusvankempen/slack-wxo-mcp-gateway](https://github.com/markusvankempen/slack-wxo-mcp-gateway)  
**Author:** [Markus van Kempen](https://github.com/markusvankempen)

Choose **one** deployment path. Each has its own directory so steps, URLs, and pitfalls stay distinct.

| Path | Directory | When to use |
|------|-----------|-------------|
| **Local + ngrok** | [`local-ngrok/`](local-ngrok/) | Dev / demo on your laptop; public HTTPS via ngrok tunnel |
| **IBM Code Engine** | [`code-engine/`](code-engine/) | Always-on hosted gateway; stable URL for Slack + WxO |

Shared (both paths):

- [SETUP.md](../SETUP.md) — Slack scopes, WxO agents, env overview  
- [USE_CASES.md](../USE_CASES.md) — real-world scenarios  
- [config.example.yaml](../config.example.yaml) · [.env.example](../.env.example)  
- Example agents: [`agent.yaml`](../agent.yaml), [`agents/`](../agents/)
