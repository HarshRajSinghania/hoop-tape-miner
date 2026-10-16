"""Pass 3: jersey number recognition per tracklet with a local VLM (Qwen3-VL, 4-bit)."""
from __future__ import annotations

import re
from collections import Counter

import cv2
import numpy as np
import pandas as pd
import torch

from .device import device

VLM_ID = "Qwen/Qwen3-VL-4B-Instruct"
PROMPT = ("What number is printed on this basketball player's jersey? "
          "Reply with only the number (e.g. 17). If no number is clearly legible reply: none")


def pick_crops(tr: pd.DataFrame, all_df: pd.DataFrame, k=4) -> pd.DataFrame:
    """Pick k large, well-separated, unoccluded detections spread over the tracklet."""
    tr = tr.assign(h=tr.y2 - tr.y1).query("h > 60")
    if tr.empty:
        return tr
    # occlusion: another person box overlapping this one in the same frame
    by_frame = {f: g for f, g in all_df[all_df.frame.isin(tr.frame)].groupby("frame")}  # group once, not per row
    clean = []
    for idx, r in tr.iterrows():
        o = by_frame.get(r.frame, all_df.iloc[:0])
        o = o[o.index != idx]
        ix = np.clip(np.minimum(o.x2, r.x2) - np.maximum(o.x1, r.x1), 0, None)
        iy = np.clip(np.minimum(o.y2, r.y2) - np.maximum(o.y1, r.y1), 0, None)
        frac = (ix * iy).max() / ((r.x2 - r.x1) * (r.y2 - r.y1)) if len(o) else 0
        clean.append(frac < 0.15)
    tr = tr[np.array(clean)]
    if tr.empty:
        return tr
    tr = tr.sort_values("frame")
    parts = np.array_split(np.arange(len(tr)), min(k, len(tr)))
    return pd.DataFrame([tr.iloc[ix].sort_values("h").iloc[-1] for ix in parts if len(ix)])


def upper_body(img: np.ndarray, r, height=256) -> np.ndarray | None:
    """Jersey region (top ~60% of the box), upscaled so digits are ~40px tall."""
    x1, y1, x2, y2 = int(r.x1), int(r.y1), int(r.x2), int(r.y2)
    pad = int(0.1 * (x2 - x1))
    c = img[max(y1, 0):int(y1 + 0.6 * (y2 - y1)), max(x1 - pad, 0):x2 + pad]
    if c.size == 0:
        return None
    s = height / c.shape[0]
    return cv2.resize(c, (int(c.shape[1] * s), height), interpolation=cv2.INTER_CUBIC)


class JerseyReader:
    def __init__(self):
        from transformers import AutoProcessor, BitsAndBytesConfig, Qwen3VLForConditionalGeneration
        self.processor = AutoProcessor.from_pretrained(VLM_ID)
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            VLM_ID, quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16,
                                                           bnb_4bit_quant_type="nf4"),
            device_map=device()).eval()  # 4-bit bitsandbytes still needs CUDA in practice

    @torch.no_grad()
    def read(self, bgr_grid: np.ndarray) -> str:
        from PIL import Image
        img = Image.fromarray(bgr_grid[:, :, ::-1])
        msgs = [{"role": "user", "content": [{"type": "image", "image": img}, {"type": "text", "text": PROMPT}]}]
        inputs = self.processor.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True,
                                                    return_dict=True, return_tensors="pt").to(device())
        out = self.model.generate(**inputs, max_new_tokens=8, do_sample=False)
        txt = self.processor.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        m = re.search(r"\d{1,2}", txt)
        return m.group(0) if m else "none"


def vote(reads: list[str], min_agree=2) -> str:
    nums = [r for r in reads if r != "none"]
    if not nums:
        return "none"
    n, c = Counter(nums).most_common(1)[0]
    return n if c >= min_agree and c > len(nums) / 2 else "none"


def main(argv=None):
    import argparse
    import json
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--min-len", type=int, default=20)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)
    run = Path(args.run)
    tr = pd.read_pickle(run / "tracks.pkl")
    det = pd.read_pickle(run / "detections.pkl")
    persons = det[det.kind == "person"]
    lens = tr.groupby("track").size()
    cand = lens[lens >= args.min_len].index
    tr = tr[tr.track.isin(cand) & tr.team.isin(["us", "them"])]
    picks = {}
    for tid, g in tr.groupby("track"):
        pk = pick_crops(g, persons[persons.frame.isin(g.frame)], k=6)
        if len(pk):
            picks[tid] = pk
        if args.limit and len(picks) >= args.limit:
            break
    by_frame: dict[int, list] = {}
    for tid, pk in picks.items():
        for _, r in pk.iterrows():
            by_frame.setdefault(int(r.frame), []).append((tid, r))
    need = sorted(by_frame)
    print(f"{len(picks)} tracklets, {len(need)} frames to decode", flush=True)
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise OSError(f"Cannot open video: {args.video}")
    crops: dict = {tid: [] for tid in picks}  # keep only small jersey crops, not full frames
    fi = 0
    try:
        while need and fi <= need[-1]:
            if fi in by_frame:
                ok, f = cap.read()
                if not ok:
                    raise OSError(f"Cannot decode requested frame {fi}: {args.video}")
                for tid, r in by_frame[fi]:
                    c = upper_body(f, r)
                    if c is not None:
                        crops[tid].append(c)
            elif not cap.grab():
                raise OSError(f"Video ended before requested frame {need[-1]}")
            fi += 1
    finally:
        cap.release()
    reader = JerseyReader()
    out = {}
    (run / "jersey_debug").mkdir(exist_ok=True)
    for i, tid in enumerate(picks):
        cs = crops[tid]
        if not cs:
            continue
        reads = [reader.read(c) for c in cs]
        num = vote(reads)
        out[int(tid)] = dict(number=num, reads=reads)
        if i < 60:
            strip = np.hstack([cv2.resize(c, (128, 256)) for c in cs])
            cv2.imwrite(str(run / "jersey_debug" / f"{tid}_{num}_{'-'.join(reads)}.jpg"), strip)
        if i % 100 == 0:
            print(i, tid, num, reads, flush=True)
    (run / "jersey.json").write_text(json.dumps(out, indent=0))
    print(pd.Series({k: v["number"] for k, v in out.items()}).value_counts().head(30))


if __name__ == "__main__":
    main()
