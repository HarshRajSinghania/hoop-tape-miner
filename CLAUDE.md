# gem-in-game

Turns one amateur basketball game video into a coach report: CV pipeline, agent film review, written reports, narration and a single-page HTML.

- Procedure: follow `docs/playbook.md` step by step. Stage details: `docs/pipeline.md`. Writing guides: `prompts/`.
- Personal data lives in `$GEM_WORKSPACE` (default `./workspace`, gitignored); one game = `workspace/teams/<opponent-slug>/<date>/`.
- Your own machine-specific rules go in `CLAUDE.local.md` (gitignored, auto-loaded).

## Working rules

- One game per session. Start by reading `git status` and the game's `game.json`; reuse an existing `run/`, do not re-run the CV pass.
- Long runs: redirect output to `workspace/logs/*.log` and read only the tail.
- Film review: one subagent per part, at most 3 subagents at once; they write files and reply in a few lines.
- Browser checks and screenshots go to the `browser-check` subagent (text result only).
- Do not switch model or toggle MCP servers/plugins mid-session (invalidates the prompt cache).
- Never invent a game result; "unclear" and "likely" are valid answers.

## Privacy (see `docs/privacy.md`)

- Never commit or push `workspace/`, videos, frames, audio, rosters, names or official stats. Check `git status` before any commit.
- Never print or commit credentials.
- Players may be minors: frames of players are shared only with the team, with consent.

# Compact instructions

Keep: decisions made, file paths, video alignment offsets, official game result, open TODOs. Drop: tool output, logs, screenshots.
