# altomfotball

Football data comes from the NIFS API (`v2api.nifs.no`). Before calling it or writing code against it, read [`docs/nifs-api.md`](docs/nifs-api.md): request rules (cache-poisoning 406s, rate limit, silent route fallback), routes, ids, match-event codes, recipes for tables, fixtures, match reports and player stats.

Tipping coupons come from the Norsk Tipping API. Before using it or linking its teams or matches to NIFS, read [`docs/norsk-tipping-api.md`](docs/norsk-tipping-api.md): the endpoint shape, the NT→NIFS match join, and the team map in `data/nt-nifs-teams.json`.

## Coupon pages

One phone-first Norwegian page per Norsk Tipping coupon (`SATURDAY`, `SUNDAY`, `MIDWEEK`). Python 3 stdlib only.

1. `python3 -m altomfotball facts DAY` writes `coupons/<salestop-date>-<day>/facts.json`: per match, both teams' table, home/away records, all-competition form, goal timing, players in form, inferred absences, head-to-head, and Oddsen H/U/B odds ([`docs/oddsen-api.md`](docs/oddsen-api.md)).
2. Write `coupons/<…>/analysis.json`: our *reading* of the numbers, not a restatement of them. The page shows no raw stats and no probabilities of our own; Oddsen's odds are the reference. Bokmål for a Norwegian tipping audience.
   - `_coupon`: `headline`, `intro` (paragraphs): where the public and the odds disagree most.
   - Per match, keyed by NT `gameEngineEventId`: `headline`, `take` (two paragraphs), `signal` (`[{stat, text}]`, shown as «Tallene som støtter oddsen»: data that *supports the odds*, i.e. why the favourite is favourite or why the odds see a close match), `noise` (`[{stat, text}]`, shown as «Dette kan snu kampen»: what could *turn the match the other way*, such as luck that may run out, absences, fatigue or a strength the odds underrate), `crowd` (how the public's split differs from the odds).
   - Separate quality from luck with `underlying` in `facts.json`: xG vs goals, shots on target for and against, conversion, save %, PDO (1,00 is neutral), plus `restDays` and `table.withdrawnPoints`. Compare with league averages (≈0,34 goals per shot on target).
   - The tendens is computed by `render.tendens()` from `facts.json` `odds.implied` against the public's split; don't write one.
   - Every number must come from `facts.json`. Check each claim against it before rendering, and re-run `facts` first if tables may have moved (Friday matches).
3. `python3 -m altomfotball render DAY` writes `site/<…>.html`.

Absences are inferred (red card or ban-triggering yellow in the last league match, regulars missing from the last squad), never official. The ban rules per league are `BAN_THRESHOLDS` in `altomfotball/analysis.py`; the pages say they are computed.
