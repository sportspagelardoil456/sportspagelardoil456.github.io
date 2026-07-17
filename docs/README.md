# Documentation index

**Author:** Markus van Kempen  
**Email:** [mvankempen@ca.ibm.com](mailto:mvankempen@ca.ibm.com) · [markus.van.kempen@gmail.com](mailto:markus.van.kempen@gmail.com)  
**Web:** [https://markusvankempen.github.io/](https://markusvankempen.github.io/) · [GitHub](https://github.com/markusvankempen)

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
