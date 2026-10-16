"""Where per-game data lives: a gitignored workspace, never the repo's tracked files.

Layout: <workspace>/teams/<opponent-slug>/<date>/  game.json, official.json, README*.md, figures, run/
The workspace root is $GEM_WORKSPACE when set, else ./workspace (relative to the current directory).
"""
from __future__ import annotations

import os
import re
from pathlib import Path


def root() -> Path:
    env = os.environ.get("GEM_WORKSPACE")
    return Path(env).expanduser() if env else Path.cwd() / "workspace"


def slug(name: str) -> str:
    """Folder name for a team: lowercase, runs of whitespace -> '-' ("Red Foxes" -> "red-foxes")."""
    return re.sub(r"\s+", "-", name.strip().lower())


def team_dir(opponent: str) -> Path:
    return root() / "teams" / slug(opponent)


def game_dir(opponent: str, date: str) -> Path:
    return team_dir(opponent) / date
