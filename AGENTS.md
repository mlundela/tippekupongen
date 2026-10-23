# altomfotball

Football data comes from the NIFS API (`v2api.nifs.no`). Before calling it or writing code against it, read [`docs/nifs-api.md`](docs/nifs-api.md): request rules (cache-poisoning 406s, silent route fallback), routes, ids, match-event codes, recipes for tables, fixtures, match reports and player stats.

Tipping coupons come from the Norsk Tipping API. Before using it or linking its teams or matches to NIFS, read [`docs/norsk-tipping-api.md`](docs/norsk-tipping-api.md): the endpoint shape, the NT→NIFS match join, and the team map in `data/nt-nifs-teams.json`.
