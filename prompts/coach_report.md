# Writing the coach report (README.md + README.en.md)

Audience: the players and coach of an amateur team, reading on a phone, often in a group chat. Goal: they understand why the game went the way it did and know what to practise this week.

## Inputs (read these, not the raw sheets)

- `game.json`, `run/official.json` (if any), `run/review_v1/summary.json`, `run/review_v1/plusminus.json`, `players_facts.md`, focus players' `player<N>_facts.md`, the `memo_part<N>.md` files, the momentum figure (`gem-in-game momentum`).
- Every number and every video time in the report must come from these files. If a fact is not there, leave it out or mark it "likely".

## Section skeleton

Keep the headings and order. The HTML page uses the H1 as page title and turns each H2 into a table-of-contents entry, so: exactly one H1, sections as H2, sub-points as H3.

```
# Coach's review: {us_team} {us_score}–{them_score} {them_team} ({date})

Us = {us_colour} {us_team} (home/away). Them = {them_colour} {them_team}. All times are **video time** (full video mm:ss), not the game clock.

**In one sentence: <where the game was won or lost, the biggest cause in numbers, and what worked>.**

| Score (us–them) | First half a–b · Second half c–d · Final **x–y** |
|---|---|
| Free-throw points | ... |
| Fouls | ... |
| Threes made | ... |

![momentum](momentum.en.png)        (README.md: momentum.png, rendered with --lang zh)

Sources: **official** = <league feed, what it records>; **film** = review of N possessions and M trips. <What is estimated; jersey-reading accuracy; what "likely" means.>

---

## 1. Game flow and momentum
- Table of 3-5 stretches: label, video time, score in the stretch, what happened.
- The decisive run, point by point: table of every opposing score in it (official time, score, how we gave it up, type), then totals by type.
- Our offence in the same stretch, in counts (possessions, points, ball screens, ball stops, isolations, transition trips and points).
- Check the team's own theory (e.g. "it was the substitutions") against the film and say plainly whether it holds.
- Comparison table: the bad stretch vs the good stretch, 3-5 rows.

## 2. Scouting report: how {them_team} play
### How they score (in order of importance)
### Key players   (table: #, official points, how to guard)
### How they defend

## 3. How we played and what went wrong
Numbered list, each item with a count and 1-3 video times. End with "What worked (keep doing it)".

## 4. Game plan for the next game against {them_team}
**Defence (top priority)** · **Offence** · **Rotation**: numbered, each rule one line, phrased as an instruction.

## 5. Team practice priorities (in order)
Table: #, focus, drill, measurable target.

## 6. Player-by-player review and practice plan
- 2-3 notes (minutes are estimates; official sheet limits; team problems are not one player's fault).
- Summary table: #, official line, est. minutes (video), one line.
- One H3 per player who played, most minutes first: **Went well** (first, with times) · **Fix** (with times) · **Practice** (two drills, each with a measurable target).
- Roster players the film cannot identify: one short line inviting them to say when they played.
```

## Writing rules

1. **No possession ids, trip ids or file names** in the text. Refer to plays by video time (`12:05`, or `24:10–24:18` for a range). Readers rewatch by time.
2. **No methods appendix.** One "Sources" line under the scoreboard is all the method the reader sees. No talk of CV, clusters, models, pipelines or tokens.
3. Numbers before adjectives: "10 of their 16 points in that stretch came on the break", not "we struggled in transition".
4. Honest uncertainty: "likely #N" when the jersey was unreadable; "unclear" when the film does not show it. Never assign an undecided basket to make totals add up.
5. Every criticism has a video time; every fix has a drill; every drill has a measurable target (count, percentage or time).
6. Start each player's section with what went well. Criticise decisions and habits, not people. Team failures (e.g. nobody back on defence) are framed as team failures.
7. Refer to players by jersey number only, never by name.
8. Plain words for amateur players; short sentences; coaching terms only when the drill uses them.
9. Tables at most 4-5 columns so they fit a phone. Images by relative file name next to the README.
10. No local paths and no links into the repo or the workspace.
11. **Both languages, each a complete file**: `README.md` in Chinese and `README.en.md` in English (the HTML page currently reads exactly these two). Same facts, numbers, times and section order; write each naturally in its language rather than translating word for word. Headings carry the same section numbers in every language.
12. Length: roughly 2,500-3,500 words per language. Cut prose before cutting evidence.

## Before you finish

- Recount every total you state against `official.json` / `game.json`.
- Check that every video time you cite exists in the facts sheets.
- Grep both files for `P0`, `pid`, `trip`, `.json`, `run/`: none should remain.
