# hoop-tape-miner docs

hoop-tape-miner is AI basketball video analysis for amateur and club teams. A local computer-vision pipeline (player and ball detection, court mapping, team split, tracking, jersey numbers, possessions) feeds an AI-agent film review (Claude Code or Codex), which writes a coach report, player reviews, an opponent scouting report, charts, narration and one shareable HTML page.

Start with the [project README](../README.md) ([中文](../README.zh.md)) for what you get and the quick start.

| Doc | For | What's in it |
|---|---|---|
| [playbook.md](playbook.md) | users and AI agents | The step-by-step procedure from one game video to the finished report |
| [pipeline.md](pipeline.md) | contributors | Every stage, its inputs and outputs, and the design choices behind them |
| [review_protocol.md](review_protocol.md) | contributors | The optional possession event review that feeds the shot charts |
| [privacy.md](privacy.md) | everyone | What stays in `workspace/`, sharing reports, minors and consent |
| [research.md](research.md) | contributors | Open-source projects and papers this builds on, and what was adapted |
| [optimization-backlog.md](optimization-backlog.md) | contributors | Measured speed and cost improvements, done and to do |

Writing guides the agent uses for each report are in [`prompts/`](../prompts/). To contribute, see [CONTRIBUTING.md](../CONTRIBUTING.md).
