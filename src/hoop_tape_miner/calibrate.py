"""Court calibration keyframes (keyframes.json) for `extract --calib` / `recalib --calib`.

    hoop-tape-miner calibrate --video V --times 1020 --out calib/                    # click points in a window
    hoop-tape-miner calibrate --video V --times 1020 --points points.json --out calib/  # non-interactive
    ... --propagate 1040,1060,1150     # also track the camera forward and add keyframes at these times

For each time (s): grab the frame, take >= 4 court landmarks (clicked, or from points.json),
fit a homography, snap it onto the painted lines (court.refine_homography), and save
kf_<t>.png + ov_<t>.jpg (overlay to eyeball). points.json:
    {"1020": [{"name": "L_lane_base_far", "px": [180, 355]}, {"court": [14, 15], "px": [1137, 282]}]}
`name` is one of LANDMARKS (court metres: x along the length from the left baseline, y from
the near/camera sideline); `court` gives raw coordinates. Interactive picks are saved to
<out>/points.json so a re-run can be non-interactive. Image paths in keyframes.json are
relative to the keyframes file; use `load_keyframes`/`load_bank` to read it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from .camera import CourtCameraTracker, KeyframeBank
from .court import CENTER_CIRCLE_R, FT_LINE, LANE_WIDTH, LENGTH, WIDTH, court_polylines, draw_court_overlay, \
    refine_homography

_LN, _LF, _M = WIDTH / 2 - LANE_WIDTH / 2, WIDTH / 2 + LANE_WIDTH / 2, LENGTH / 2
LANDMARKS = {
    "L_corner_near": ((0, 0), "left baseline x near sideline"),
    "L_corner_far": ((0, WIDTH), "left baseline x far sideline"),
    "L_lane_base_near": ((0, _LN), "left lane line x baseline (near side)"),
    "L_lane_base_far": ((0, _LF), "left lane line x baseline (far side)"),
    "L_ft_near": ((FT_LINE, _LN), "left free-throw line, near end"),
    "L_ft_far": ((FT_LINE, _LF), "left free-throw line, far end"),
    "mid_near": ((_M, 0), "halfway line x near sideline"),
    "mid_far": ((_M, WIDTH), "halfway line x far sideline"),
    "circle_near": ((_M, WIDTH / 2 - CENTER_CIRCLE_R), "centre circle x halfway line (near)"),
    "circle_far": ((_M, WIDTH / 2 + CENTER_CIRCLE_R), "centre circle x halfway line (far)"),
    "R_ft_far": ((LENGTH - FT_LINE, _LF), "right free-throw line, far end"),
    "R_ft_near": ((LENGTH - FT_LINE, _LN), "right free-throw line, near end"),
    "R_lane_base_far": ((LENGTH, _LF), "right lane line x baseline (far side)"),
    "R_lane_base_near": ((LENGTH, _LN), "right lane line x baseline (near side)"),
    "R_corner_far": ((LENGTH, WIDTH), "right baseline x far sideline"),
    "R_corner_near": ((LENGTH, 0), "right baseline x near sideline"),
}


def court_xy(p: dict) -> tuple[float, float]:
    return tuple(p["court"]) if "court" in p else LANDMARKS[p["name"]][0]


def fit(img, points: list[dict], iters=3):
    """Points -> (H court->image refined on painted lines, median residual px, support)."""
    if len(points) < 4:
        raise ValueError("need >= 4 points")
    court = np.float32([court_xy(p) for p in points])
    pix = np.float32([p["px"] for p in points])
    H0, _ = cv2.findHomography(court, pix)
    return refine_homography(img, H0, iters=iters)


def _minimap(target, scale=9, pad=6):
    w, h = int(LENGTH * scale) + 2 * pad, int(WIDTH * scale) + 2 * pad
    m = np.full((h, w, 3), 40, np.uint8)

    def px(x, y):
        return int(pad + x * scale), int(pad + (WIDTH - y) * scale)  # near sideline at the bottom
    for pl in court_polylines():
        cv2.polylines(m, [np.int32([px(x, y) for x, y in pl])], False, (230, 230, 230), 1)
    cv2.circle(m, px(*target), 5, (0, 0, 255), -1)
    return m


def pick_points(img, title="calibrate") -> list[dict]:
    """OpenCV window: click each highlighted landmark; s=skip, u=undo, Enter=done (>= 4), Esc=abort."""
    names, picked, clicks, i = list(LANDMARKS), {}, [], 0
    cv2.namedWindow(title, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(title, lambda ev, x, y, *_: clicks.append((x, y)) if ev == cv2.EVENT_LBUTTONDOWN else None)
    while True:
        vis = img.copy()
        for n, (x, y) in picked.items():
            cv2.circle(vis, (x, y), 5, (0, 0, 255), -1)
            cv2.putText(vis, n, (x + 6, y - 6), 0, 0.5, (0, 255, 255), 1)
        msg = (f"Click: {LANDMARKS[names[i]][1]}  (red dot on map)" if i < len(names) else "All landmarks offered")
        lines = [msg, f"[s] skip (not visible)  [u] undo  [Enter] done ({len(picked)} picked, need >= 4)  [Esc] abort"]
        cv2.rectangle(vis, (0, 0), (vis.shape[1], 52), (0, 0, 0), -1)
        for k, t in enumerate(lines):
            cv2.putText(vis, t, (8, 20 + 24 * k), 0, 0.6, (255, 255, 255), 1)
        if i < len(names):
            mm = _minimap(LANDMARKS[names[i]][0])
            vis[56:56 + mm.shape[0], vis.shape[1] - mm.shape[1] - 4:vis.shape[1] - 4] = mm
        cv2.imshow(title, vis)
        key = cv2.waitKey(30) & 0xFF
        if clicks and i < len(names):
            picked[names[i]] = clicks.pop()
            i += 1
        elif key == ord("s") and i < len(names):
            i += 1
        elif key == ord("u") and i > 0:
            i -= 1
            picked.pop(names[i], None)
        elif key in (10, 13) and len(picked) >= 4:
            break
        elif key == 27:
            cv2.destroyWindow(title)
            raise SystemExit("aborted")
        if i >= len(names):
            clicks.clear()
    cv2.destroyWindow(title)
    return [{"name": n, "px": [int(x), int(y)]} for n, (x, y) in picked.items()]


def grab(cap, t: float):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * cap.get(cv2.CAP_PROP_FPS))))
    ok, f = cap.read()
    if not ok:
        raise SystemExit(f"cannot read frame at {t} s")
    return f


def propagate(cap, keyframes: list[dict], targets: list[float], start: float, step=6, max_q=3.0):
    """Track the camera from `start` to the last target; return {t: (frame, H, q)} for targets with q < max_q."""
    bank = KeyframeBank()
    for kf in keyframes:
        bank.add(cv2.cvtColor(kf["img"], cv2.COLOR_BGR2GRAY), np.array(kf["H"]))
    trk = CourtCameraTracker(bank)
    fps = cap.get(cv2.CAP_PROP_FPS)
    f0, todo, got = int(round(start * fps)), sorted(targets), {}
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)
    for fi in range(f0, int(round(todo[-1] * fps)) + 1):
        ok, fr = cap.read()
        if not ok:
            break
        if (fi - f0) % step:
            continue
        H, q, how = trk.update(fr, [])
        while todo and fi >= round(todo[0] * fps):
            t = todo.pop(0)
            print(f"  t={t:g} q={q:.2f} via {how}" + ("" if H is not None and q < max_q else "  -> skipped"))
            if H is not None and q < max_q:
                got[t] = (fr, H.copy(), q)
    return got


def load_keyframes(path) -> list[dict]:
    """keyframes.json -> [{img, H, ...}], image paths resolved relative to the file."""
    path = Path(path)
    out = []
    for kf in json.loads(path.read_text(encoding="utf-8")):
        img = cv2.imread(str(path.parent / kf["image"]))  # absolute paths survive the join
        if img is None:
            raise FileNotFoundError(path.parent / kf["image"])
        out.append({**kf, "img": img})
    return out


def load_bank(path) -> KeyframeBank:
    bank = KeyframeBank()
    for kf in load_keyframes(path):
        bank.add(cv2.cvtColor(kf["img"], cv2.COLOR_BGR2GRAY), np.array(kf["H"]))
    return bank


def main(argv=None):
    ap = argparse.ArgumentParser(prog="hoop-tape-miner calibrate", description=__doc__.splitlines()[0])
    ap.add_argument("--video", required=True)
    ap.add_argument("--times", required=True, help="comma-separated seconds of frames to calibrate by hand")
    ap.add_argument("--out", required=True, help="directory for keyframes.json + images")
    ap.add_argument("--points", help="points.json (non-interactive)")
    ap.add_argument("--propagate", default="", help="comma-separated seconds: extra keyframes by camera tracking")
    ap.add_argument("--step", type=int, default=6, help="track every Nth video frame when propagating")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(a.video)
    given = json.loads(Path(a.points).read_text(encoding="utf-8")) if a.points else {}
    picked, kfs = dict(given), []
    for t in [float(x) for x in a.times.split(",")]:
        key = f"{t:g}"
        img = grab(cap, t)
        if key not in picked:
            if a.points:
                raise SystemExit(f"no points for t={key} in {a.points}")
            picked[key] = pick_points(img, f"calibrate t={key}s")
            (out / "points.json").write_text(json.dumps(picked, indent=1), encoding="utf-8")
        H, med, sup = fit(img, picked[key])
        print(f"t={key}: median residual {med:.2f} px, support {sup}" + ("  (WEAK: check overlay)" if sup < 120 or med > 3 else ""))
        kfs.append(dict(t=t, img=img, H=H, median_px=round(med, 2), support=sup, source="points"))
    if a.propagate:
        targets = [float(x) for x in a.propagate.split(",")]
        print("propagating from", min(k["t"] for k in kfs))
        for t, (fr, H, q) in propagate(cap, kfs, targets, min(k["t"] for k in kfs), a.step).items():
            kfs.append(dict(t=t, img=fr, H=H, median_px=round(q, 2), source="propagated"))
    entries = []
    for kf in kfs:
        name = f"kf_{kf['t']:g}.png"
        cv2.imwrite(str(out / name), kf["img"])
        cv2.imwrite(str(out / f"ov_{kf['t']:g}.jpg"), draw_court_overlay(kf["img"], kf["H"]))
        entries.append({"image": name, "H": np.asarray(kf["H"]).tolist(),
                        **{k: v for k, v in kf.items() if k not in ("img", "H")}})
    (out / "keyframes.json").write_text(json.dumps(entries, indent=1), encoding="utf-8")
    print(len(entries), "keyframes ->", out / "keyframes.json")


if __name__ == "__main__":
    main()
