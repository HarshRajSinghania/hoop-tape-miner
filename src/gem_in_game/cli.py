"""`gem-in-game <stage> ...` — thin dispatcher over the pipeline stages.

Stage modules are imported lazily, so `gem-in-game html` does not load torch, and a stage whose module is
missing fails with a short message instead of breaking the whole CLI.
"""
from __future__ import annotations

import importlib
import sys

STAGES = {
    "new-game": ("gem_in_game.new_game", "scaffold workspace/teams/<opponent>/<date>/ with game.json + run/"),
    "extract": ("gem_in_game.extract", "pass 1: detection + court homography + colour features"),
    "embed": ("gem_in_game.embed", "pass 2a: SigLIP embeddings for team classification"),
    "recalib": ("gem_in_game.recalib", "re-run court homography only, reuse detections"),
    "calibrate": ("gem_in_game.calibrate", "court calibration keyframes for extract/recalib"),
    "tracks": ("gem_in_game.build_tracks", "pass 2b: team clusters + court-space tracking"),
    "jersey": ("gem_in_game.jersey", "pass 3: jersey numbers with Qwen3-VL"),
    "analyze": ("gem_in_game.analyze", "pass 4: identities, possessions, tactical metrics"),
    "review": ("gem_in_game.review", "pass 5: annotated possession sheets for event review"),
    "coach-sheets": ("gem_in_game.coach_review", "film-review sheets + lineup intervals for the coach review"),
    "merge-reviews": ("gem_in_game.merge_reviews", "merge reviewed event parts after checking sheet coverage"),
    "coach-summary": ("gem_in_game.coach_summary", "aggregate coach review trips into per-segment numbers"),
    "report": ("gem_in_game.report", "pass 6: figures + stats.json"),
    "official": ("gem_in_game.official", "league box score + score flow + video alignment"),
    "plusminus": ("gem_in_game.plusminus", "on-court plus-minus per player from lineups + official score flow"),
    "momentum": ("gem_in_game.momentum", "score-margin figure with scoring runs and on-court lanes"),
    "replay": ("gem_in_game.replay", "2D tactics-board replay (mp4) of possessions from CV tracks"),
    "narrate": ("gem_in_game.narrate", "listen.<lang>.md -> listen.<lang>.mp3 (edge-tts + ffmpeg)"),
    "html": ("gem_in_game.render_html", "report folder (README.md + README.en.md) -> one bilingual index.html"),
}


def usage() -> str:
    w = max(map(len, STAGES))
    lines = ["usage: gem-in-game <stage> [args]   (gem-in-game <stage> -h for a stage's options)", ""]
    lines += [f"  {k:{w}s}  {d}" for k, (_, d) in STAGES.items()]
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(usage())
        sys.exit(0 if argv else 1)
    if argv[0] not in STAGES:
        print(f"unknown stage {argv[0]!r}\n\n{usage()}")
        sys.exit(1)
    name = STAGES[argv[0]][0]
    try:
        mod = importlib.import_module(name)
    except ModuleNotFoundError as e:
        if e.name != name:
            raise
        sys.exit(f"stage {argv[0]!r} is not available in this checkout ({name} is missing)")
    sys.argv[0] = f"gem-in-game {argv[0]}"  # argparse prog for stages that do not set one
    mod.main(argv[1:])


if __name__ == "__main__":
    main()
