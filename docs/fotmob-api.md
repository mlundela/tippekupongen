# FotMob reference (injuries and suspensions)

FotMob's web app reads JSON from `https://www.fotmob.com/api/data/`. It is undocumented and unofficial; it may change or close without notice, and FotMob's terms likely don't cover republishing. Client: `altomfotball/fotmob.py`. Mapped on 2026-10-24.

## Endpoints (no auth)

- `matches?date=YYYYMMDD` lists every match that day, grouped in `leagues[]`. League ids: Eliteserien `59`, Premier League `47`, Championship `1000001801`. Each match has `id`, `home`/`away` `{id, name, longName}`, and `status.utcTime` (ISO, `Z`). The `time` field is in local time, so use `utcTime`.
- `matchDetails?matchId=<id>` returns the match. `content.lineup.homeTeam|awayTeam.unavailable[]` lists the players out before kickoff: `name`, `firstName`, `lastName`, `unavailability.type` (`injury` | `suspension`), `unavailability.expectedReturn` (`"Early November 2026"`, `"Doubtful"`, `"Back in training"`, `"Out for season"`, `"About a week"`, `"Unknown"`). An empty or missing list means nobody is listed.
- `api/matchDetails` without `/data/` returns 404 HTML.

- Finished matches: `content.matchFacts` has `events.events[]` (`type` Goal/Card/Substitution, `time`, `overloadTime` for added time, `nameStr`, `isHome`, `ownGoal`, `card` Yellow/Red/YellowRed, `goalDescription`), `playerOfTheMatch` (`name.fullName`, `teamName`, `rating.num`), `topPlayers`, `insights` and `highlights.url` (YouTube, most matches). `content.stats.Periods.All.stats[].stats[]` has `{title, stats: [home, away]}` for «Expected goals (xG)», «Total shots», «Shots on target», «Big chances», «Ball possession». `matchSummary` is null. There is no written report, and the live ticker (`ltc?ltcUrl=…`) returns `null`. `fotmob.match_report()` extracts these fields.

## Linking

- **Matches:** same UTC kickoff, one side named near-identically (≥ 0.9) and the other at least loosely (≥ 0.4). FotMob uses full club names («Hamarkameratene» for HamKam, «Cardiff City»), which fail the 0.6-on-both-sides rule used for NIFS and Oddsen. Result: 12/12 on the Saturday coupon of 24 Oct 2026.
- **Players to NIFS:** exact token sets first («Paik Seung-Ho» = «Seung-ho Paik»), then surname + first initial only when it picks out one remaining player. Wolves has both Bertrand and Boubacar Traoré, so a looser rule pairs the wrong one.

## How it is used

`analysis._with_availability()` overlays FotMob on the inferred absences. When FotMob has the match, it is the source for who is out: inferred suspensions, «missing from last squad» and «returning» are dropped, while card risk (one yellow from a ban, computed from NIFS) stays. When FotMob has no match, the inferred absences remain and `absenceSource` is `beregnet`.

Spot checks on 24 Oct 2026: FotMob confirmed the inferred bans of Osho, Sessegnon, Draper and Elerewe. It corrected «returning» for Bentancur and Hamer (both still banned) and «missing» for Chiakha (he had served a ban). It also added injuries NIFS can't show (Saka, Saliba, Larin). For Premier League matches, `fantasy.premierleague.com/api/bootstrap-static/` (`elements[].status/news/chance_of_playing_next_round`) agreed on every case checked.
