"""Coach film-review sheets: 2x2 annotated frame grids per possession with the official
score flow in the header, CV lineups per possession, and the game split into N parts
(one reviewer each) with a filled-in brief per part.

    gem-in-game coach-sheets --run RUN --game game.json --official official.json \
        --out RUN/review_v1 [--parts 6] [--video V] [--brief prompts/film_review_brief.md] [--skip-sheets]
    gem-in-game coach-sheets zoom SHEET TILE X Y W H OUT [--scale 3]   # close-up crop of one tile

Reads RUN/tracks.pkl, possessions.pkl, player_numbers.json. Writes to --out: p<pid>_<k>.jpg,
manifest.json, part<N>.json, lineup_intervals.json, brief_part<N>.md (if the brief template
exists). Sheet paths in the json files are relative to --out. Optional game.json "review"
block overrides the layout: every, pre, post, tile [w, h], grid [cols, rows], header,
lineup_gap, lineup_min. Brief placeholders ({us_team}, {review_dir}, {official_totals}, {part},
{t0}, ...; see brief_values) come from game.json + official.json; a game.json "brief" block
overrides any of them (e.g. "watch_notes", "competition", "memo_language").
Official stats are optional: without --official (and no official.json next to game.json or in RUN) the
sheets carry no score flow and reviewers work from the recording alone.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .review import annotate, use_game

LAYOUT = dict(every=1.0, pre=1.0, post=3.0, tile=[800, 450], grid=[2, 2], header=28, quality=82,
              lineup_gap=25.0, lineup_min=8.0, window_pad=8.0)
BRIEF = Path(__file__).resolve().parents[2] / "prompts" / "film_review_brief.md"


def mmss(s: float) -> str:
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


def _num_key(n: str):
    return int(n) if str(n).isdigit() else 999


def intervals(ts, gap=25.0, min_len=8.0) -> list[tuple[float, float]]:
    """Sighting times -> on-court intervals: fill gaps <= `gap` s, drop intervals < `min_len` s."""
    ts = np.sort(np.asarray(ts, float))
    if not len(ts):
        return []
    segs, s, p = [], ts[0], ts[0]
    for t in ts[1:]:
        if t - p > gap:
            segs.append((s, p))
            s = t
        p = t
    segs.append((s, p))
    return [(float(a), float(b)) for a, b in segs if b - a >= min_len]


def lineup_intervals(tracks: pd.DataFrame, periods=None, rosters=None, gap=25.0, min_len=8.0) -> dict:
    """{"team#number": [(t0, t1), ...]} from jersey-identified track rows, per period, roster-gated."""
    d = tracks[tracks.number.notna() & tracks.team.isin(["us", "them"])]
    periods = periods or [(float(d.t.min()), float(d.t.max()))]
    out = {}
    for (team, n), g in d.groupby(["team", "number"]):
        n = str(n)
        if rosters and team in rosters and n not in {str(x) for x in rosters[team]}:
            continue
        segs = []
        for a, b in periods:
            segs += intervals(g.t[(g.t >= a) & (g.t <= b)].to_numpy(), gap, min_len)
        if segs:
            out[f"{team}#{n}"] = segs
    return out


def on_court(lineup: dict, t0: float, t1: float, min_overlap=0.3) -> dict:
    """Numbers whose interval covers > min_overlap of [t0, t1]."""
    res = {"us": [], "them": []}
    for k, segs in lineup.items():
        team, n = k.split("#")
        if any(a <= t1 and b >= t0 and min(b, t1) - max(a, t0) > min_overlap * (t1 - t0) for a, b in segs):
            res[team].append(n)
    return {k: sorted(v, key=_num_key) for k, v in res.items()}


def window_events(flow: list[dict], t0: float, t1: float) -> list[dict]:
    keys = ("our_video_t", "team", "points", "score_us", "score_them")
    return [{k: e[k] for k in keys} for e in flow
            if e.get("our_video_t") is not None and t0 <= e["our_video_t"] <= t1]


def events_text(ev: list[dict]) -> str:
    return "; ".join(f'{e["team"]} +{e["points"]} @~{mmss(e["our_video_t"])} ({e["score_us"]}-{e["score_them"]})'
                     for e in ev) or "no official scoring in window"


def split_parts(manifest: list[dict], n: int) -> list[list[dict]]:
    """Contiguous parts with roughly equal sheet counts."""
    tot = sum(len(m["sheets"]) for m in manifest) or 1
    parts, acc = [[] for _ in range(n)], 0
    for m in manifest:
        parts[min(n - 1, int(acc / (tot / n)))].append(m)
        acc += len(m["sheets"])
    return [p for p in parts if p]


def fill_brief(template: str, values: dict, part: int | None = None) -> str:
    """str.replace each {key} (JSON braces stay intact); drop a leading <!-- --> template note;
    with `part`, the generic file names partN.json / memo_partN.md become part<part>..."""
    template = re.sub(r"<!--.*?-->\n*", "", template, count=1, flags=re.S)
    for k, v in values.items():
        template = template.replace("{" + k + "}", str(v))
    return template.replace("partN", f"part{part}") if part else template


def official_summary(official: dict, game: dict) -> str:
    """One-line official totals + scorers per team for the brief."""
    fin, tot = official.get("final", {}), official.get("totals", {})
    ht = game.get("result", {}).get("halftime")
    s = [f"Final {fin.get('us', {}).get('pts', '?')}-{fin.get('them', {}).get('pts', '?')} (us-them)"
         + (f", halftime {ht['us']}-{ht['them']}" if ht else "")]
    for side in ("us", "them"):
        t = tot.get(side)
        if not t:
            continue
        made = lambda k: t.get(k, {}).get("made", 0)  # noqa: E731
        scorers = sorted(((n, p.get("PTS", 0)) for n, p in official.get("players", {}).get(side, {}).items()
                          if p.get("PTS")), key=lambda x: -x[1])
        s.append(f"{side}: made FG {made('FGM-A')} ({made('2PM-A')} twos, {made('3PM-A')} threes), FT {made('FTM-A')}, "
                 f"fouls {t.get('PF', '?')}; scorers " + ", ".join(f"#{n} {p}" for n, p in scorers))
    return ". ".join(s)


def load_official(path: str | None, game_path: Path, run: Path | None = None) -> dict:
    """official.json if there is one; otherwise an empty score flow, so the review runs from the recording alone."""
    if path:
        if not Path(path).is_file():
            raise SystemExit(f"official stats not found: {path}")
        return json.loads(Path(path).read_text(encoding="utf-8"))
    for p in [game_path.parent / "official.json"] + ([run / "official.json"] if run else []):
        if p.is_file():
            print("official stats:", p)
            return json.loads(p.read_text(encoding="utf-8"))
    print("note: no official stats (no official.json next to game.json or in the run dir); sheets will have no score flow "
          "and the review works from the recording alone. Add one later with `gem-in-game official`.")
    return {"score_flow": []}


def brief_values(game: dict, official: dict, out: Path) -> dict:
    """Placeholder values from game.json / official.json; optional game.json "brief" block overrides."""
    m = re.match(r"\d{4}-\d{2}-\d{2}", game.get("name", ""))
    focus = game["us"].get("focus_players") or game["us"].get("focus_player")
    vals = dict(us_team=game["us"].get("team", "us"), them_team=game["them"].get("team", "them"),
                us_colour=game["us"].get("colour", ""), them_colour=game["them"].get("colour", ""),
                us_box="PURPLE", them_box="GREEN", game_date=game.get("date") or (m.group(0) if m else ""),
                competition=game.get("competition", "amateur league game"),
                official_totals=official_summary(official, game) if official.get("totals") else "not available",
                watch_notes=game.get("watch_notes", ""), memo_language=game.get("memo_language", "English"),
                focus_players=", ".join(f"#{x}" for x in ([focus] if isinstance(focus, str) else focus or [])) or "none",
                review_dir=out.resolve().as_posix(), out_dir=out.resolve().as_posix())
    return {**vals, **game.get("brief", {})}


def compose(tiles: list[np.ndarray], header: str, lay: dict) -> np.ndarray:
    cols, rows = lay["grid"]
    blank = np.zeros_like(tiles[0])
    tiles = tiles + [blank] * (cols * rows - len(tiles))
    sheet = np.vstack([np.hstack(tiles[r * cols:(r + 1) * cols]) for r in range(rows)])
    hdr = np.zeros((lay["header"], sheet.shape[1], 3), np.uint8)
    cv2.putText(hdr, header[:150], (4, lay["header"] - 8), 0, 0.55, (255, 255, 255), 1)
    return np.vstack([hdr, sheet])


def build_sheets(cap, tracks, poss, numbers, flow, lineup, out: Path, lay: dict) -> list[dict]:
    fps = cap.get(cv2.CAP_PROP_FPS)
    by_frame = {f: g for f, g in tracks.groupby("frame")}
    analysed = np.array(sorted(by_frame))
    per_sheet = lay["grid"][0] * lay["grid"][1]
    manifest = []
    for pid, p in poss.iterrows():
        t0, t1 = p.start - lay["pre"], p.end + lay["post"]
        ev = window_events(flow, t0 - lay["window_pad"], t1 + lay["window_pad"])
        tiles = []
        for t in np.arange(max(t0, 0.0), t1, lay["every"]):
            fi = int(round(t * fps))
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, f = cap.read()
            if not ok:
                continue
            near = analysed[np.abs(analysed - fi).argmin()]
            img = annotate(f, by_frame[near], numbers) if abs(near - fi) <= 6 else f
            img = cv2.resize(img, tuple(lay["tile"]))
            cv2.rectangle(img, (0, 0), (120, 24), (0, 0, 0), -1)
            m, s = divmod(t, 60)
            cv2.putText(img, f"{int(m):02d}:{s:04.1f}", (4, 18), 0, 0.6, (0, 255, 255), 2)
            tiles.append(img)
        head = f"P{pid:03d} {p.side} half, CV offence={p.offence} | OFFICIAL: {events_text(ev)}"
        sheets = []
        for k in range(0, len(tiles), per_sheet):
            name = f"p{pid:03d}_{k // per_sheet}.jpg"
            cv2.imwrite(str(out / name), compose(tiles[k:k + per_sheet], head, lay),
                        [cv2.IMWRITE_JPEG_QUALITY, lay["quality"]])
            sheets.append(name)
        manifest.append(dict(pid=int(pid), start=round(float(p.start), 1), end=round(float(p.end), 1),
                             side=p.side, cv_offence=p.offence, period=int(p.period), official_events=ev,
                             on_court=on_court(lineup, p.start, p.end), sheets=sheets))
    return manifest


def zoom(sheet, tile, x, y, w, h, out, grid=(2, 2), header=28, scale=3):
    """Crop (x, y, w, h) inside tile `tile` (row-major) of a sheet and upscale it (Lanczos)."""
    img = cv2.imread(str(sheet))
    tw, th = img.shape[1] // grid[0], (img.shape[0] - header) // grid[1]
    tx, ty = (tile % grid[0]) * tw, header + (tile // grid[0]) * th
    crop = img[ty + y:ty + y + h, tx + x:tx + x + w]
    cv2.imwrite(str(out), cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4))


def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["zoom"]:
        zp = argparse.ArgumentParser(prog="gem-in-game coach-sheets zoom")
        for k in ("sheet", "tile", "x", "y", "w", "h", "out"):
            zp.add_argument(k, type=int if k in "tile x y w h".split() else str)
        zp.add_argument("--scale", type=float, default=3)
        z = zp.parse_args(argv[1:])
        Path(z.out).parent.mkdir(parents=True, exist_ok=True)
        zoom(z.sheet, z.tile, z.x, z.y, z.w, z.h, z.out, scale=z.scale)
        print("wrote", z.out)
        return
    ap = argparse.ArgumentParser(prog="gem-in-game coach-sheets", description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--official", help="league stats (default: official.json next to game.json or in --run, if any)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--parts", type=int, default=6)
    ap.add_argument("--video", help="default: game.json 'video', relative to game.json")
    ap.add_argument("--brief", default=str(BRIEF), help="brief template with {placeholders}")
    ap.add_argument("--skip-sheets", action="store_true", help="reuse --out/manifest.json; redo parts + briefs")
    a = ap.parse_args(argv)
    run, out, game_path = Path(a.run), Path(a.out), Path(a.game)
    game = json.loads(game_path.read_text(encoding="utf-8"))
    use_game(game)  # sheet outline colours from us.hex / them.hex
    lay = {**LAYOUT, **game.get("review", {})}
    official = load_official(a.official, game_path, run)
    out.mkdir(parents=True, exist_ok=True)

    if a.skip_sheets:
        manifest = json.loads((out / "manifest.json").read_text())
    else:
        video = Path(a.video or game.get("video", ""))
        if not video.is_absolute() and not a.video:
            video = game_path.parent / video
        if not video.is_file():
            raise SystemExit(f"video not found: {video} (pass --video)")
        tracks = pd.read_pickle(run / "tracks.pkl")
        poss = pd.read_pickle(run / "possessions.pkl")
        numbers = {int(k): v for k, v in json.loads((run / "player_numbers.json").read_text()).items()}
        lineup = lineup_intervals(tracks, game.get("periods"), game.get("rosters"), lay["lineup_gap"],
                                  lay["lineup_min"])
        manifest = build_sheets(cv2.VideoCapture(str(video)), tracks, poss, numbers, official["score_flow"],
                                lineup, out, lay)
        (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
        (out / "lineup_intervals.json").write_text(
            json.dumps({k: [[round(x) for x in s] for s in v] for k, v in lineup.items()}, indent=0))
    print(len(manifest), "possessions", sum(len(m["sheets"]) for m in manifest), "sheets")

    parts = split_parts(manifest, a.parts)
    template = Path(a.brief).read_text(encoding="utf-8") if Path(a.brief).is_file() else None
    base = brief_values(game, official, out) if template else {}
    for i, pt in enumerate(parts, 1):
        (out / f"part{i}.json").write_text(json.dumps(pt, indent=1))
        t0, t1 = pt[0]["start"], pt[-1]["end"]
        print(i, len(pt), "poss", sum(len(m["sheets"]) for m in pt), "sheets", f"{mmss(t0)}-{mmss(t1)}")
        if template:
            vals = {**base, "part": i, "n_parts": len(parts), "t0": mmss(t0), "t1": mmss(t1)}
            (out / f"brief_part{i}.md").write_text(fill_brief(template, vals, i), encoding="utf-8")
    if not template:
        print("no brief template at", a.brief, "- skipped brief_part*.md")


if __name__ == "__main__":
    main()
