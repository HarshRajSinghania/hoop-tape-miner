"""Coach review helpers: lineup intervals, on-court sets, part split, brief filling, sheet layout."""
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gem_in_game import coach_review

from gem_in_game.coach_review import (brief_values, compose, events_text, fill_brief, intervals, lineup_intervals,
                                      on_court, split_parts, window_events)


class CoachReviewTests(unittest.TestCase):
    def test_intervals_gap_fill_and_min_length(self):
        ts = list(np.arange(0, 20, 1.0)) + [60, 61] + list(np.arange(100, 130, 2.0))
        self.assertEqual(intervals(ts, gap=25, min_len=8), [(0.0, 19.0), (100.0, 128.0)])

    def test_lineup_split_by_period_and_roster(self):
        t = np.arange(0, 60, 1.0)
        tr = pd.DataFrame({"t": np.r_[t, t, t], "team": ["us"] * 60 + ["us"] * 60 + ["them"] * 60,
                           "number": ["17"] * 60 + ["99"] * 60 + [None] * 60})
        lu = lineup_intervals(tr, periods=[(0, 29), (31, 60)], rosters={"us": ["17", 9]})
        self.assertEqual(lu, {"us#17": [(0.0, 29.0), (31.0, 59.0)]})
        self.assertEqual(on_court(lu, 10, 20), {"us": ["17"], "them": []})
        self.assertEqual(on_court(lu, 28, 40)["us"], ["17"])  # overlap 9 of 12 s

    def test_events_window_and_text(self):
        flow = [{"our_video_t": 61.5, "team": "us", "points": 2, "score_us": 2, "score_them": 0},
                {"our_video_t": None, "team": "them", "points": 2, "score_us": 2, "score_them": 2}]
        ev = window_events(flow, 50, 70)
        self.assertEqual(events_text(ev), "us +2 @~01:01 (2-0)")
        self.assertEqual(events_text([]), "no official scoring in window")

    def test_split_parts_balanced_by_sheets(self):
        man = [{"pid": i, "sheets": ["x"] * n} for i, n in enumerate([4, 4, 1, 1, 1, 1])]
        parts = split_parts(man, 2)
        self.assertEqual([[m["pid"] for m in p] for p in parts], [[0, 1], [2, 3, 4, 5]])
        self.assertEqual(len(split_parts(man[:1], 6)), 1)  # empty parts dropped

    def test_fill_brief_leaves_unknown_braces(self):
        s = fill_brief("Us {us_team} vs {them_team}, part {part}/{n_parts}; json {\"a\": 1} {other}",
                       {"us_team": "A", "them_team": "B", "part": 2, "n_parts": 6})
        self.assertEqual(s, "Us A vs B, part 2/6; json {\"a\": 1} {other}")

    def test_brief_values_and_part_names(self):
        game = {"name": "2026-10-14 league game", "us": {"team": "A", "colour": "navy", "focus_player": "17"},
                "them": {"team": "B", "colour": "teal"}, "result": {"halftime": {"us": 9, "them": 21}},
                "brief": {"watch_notes": "their #19 is misread"}}
        official = {"final": {"us": {"pts": 5}, "them": {"pts": 2}},
                    "totals": {"us": {"FGM-A": {"made": 2}, "2PM-A": {"made": 1}, "3PM-A": {"made": 1},
                                      "FTM-A": {"made": 0}, "PF": 3}},
                    "players": {"us": {"17": {"PTS": 3}, "9": {"PTS": 2}, "4": {"PTS": 0}}}}
        v = brief_values(game, official, Path("rev"))
        self.assertEqual((v["game_date"], v["focus_players"], v["watch_notes"]), ("2026-10-14", "#17", "their #19 is misread"))
        self.assertEqual(v["official_totals"], "Final 5-2 (us-them), halftime 9-21. us: made FG 2 (1 twos, 1 threes), "
                                               "FT 0, fouls 3; scorers #17 3, #9 2")
        s = fill_brief("# T\n\n<!--\nnote {us_team}\n-->\n\nRead {review_dir}/partN.json", v, part=3)
        self.assertEqual(s, f"# T\n\nRead {Path('rev').resolve().as_posix()}/part3.json")

    def test_compose_layout(self):
        lay = {"grid": [2, 2], "header": 28}
        sheet = compose([np.full((45, 80, 3), 255, np.uint8)] * 3, "hdr", lay)
        self.assertEqual(sheet.shape, (28 + 90, 160, 3))
        self.assertEqual(int(sheet[-1, -1].sum()), 0)  # padding tile is black


if __name__ == "__main__":
    unittest.main()


def test_official_is_optional(tmp_path, capsys):
    game = tmp_path / "game.json"
    game.write_text("{}")
    assert coach_review.load_official(None, game) == {"score_flow": []}
    assert "no official stats" in capsys.readouterr().out
    (tmp_path / "official.json").write_text('{"score_flow": [1]}')
    assert coach_review.load_official(None, game) == {"score_flow": [1]}
    with pytest.raises(SystemExit):
        coach_review.load_official(str(tmp_path / "missing.json"), game)
