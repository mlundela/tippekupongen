# altomfotball

Football data comes from the NIFS API (`v2api.nifs.no`). Before calling it or writing code against it, read [`docs/nifs-api.md`](docs/nifs-api.md): request rules (cache-poisoning 406s, rate limit, silent route fallback), routes, ids, match-event codes, recipes for tables, fixtures, match reports and player stats.

Tipping coupons come from the Norsk Tipping API. Before using it or linking its teams or matches to NIFS, read [`docs/norsk-tipping-api.md`](docs/norsk-tipping-api.md): the endpoint shape, the NT→NIFS match join, and the team map in `data/nt-nifs-teams.json`.

## Coupon pages

One phone-first Norwegian page per Norsk Tipping coupon (`SATURDAY`, `SUNDAY`, `MIDWEEK`). Python 3 stdlib only.

1. `python3 -m altomfotball facts DAY` writes `coupons/<salestop-date>-<day>/facts.json`: per match, both teams' table, home/away records, all-competition form, goal timing, players in form, inferred absences, and head-to-head.
2. Write `coupons/<…>/analysis.json`, keyed by NT `gameEngineEventId`: `tendens` (`H`, `HU`, `HUB`…), `headline`, `summary`, `facts` (3–4 bullets). Bokmål for a Norwegian tipping audience. Every number in it must come from `facts.json`; check each claim against it before rendering.
3. `python3 -m altomfotball render DAY` writes `site/<…>.html`.

Absences are inferred (red card or ban-triggering yellow in the last league match, regulars missing from the last squad), never official. The ban rules per league are `BAN_THRESHOLDS` in `altomfotball/analysis.py`; the pages say they are computed.
