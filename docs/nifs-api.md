# NIFS API reference

Football data API behind nifs.no: Norwegian and international football, 2001 to now, live during matches.
Base URL `https://v2api.nifs.no/`. No auth for GET, CORS `*`, every response is cached at Varnish for 30 min (`x-ttl: 1800`). Writes return 401.
There is no human-written documentation; this file was mapped by probing on 2026-10-23. Re-probe before trusting a route that isn't listed here.

## Request rules (every call)

1. **Send `Accept: application/json`.** A request with no `Accept` header gets a 406, and Varnish caches that 406 *at the URL for every client* for 30 min. Python `urllib` sends no `Accept` by default; curl and browsers do.
2. **On a 406, retry with a cache-busting param** (`?_=<random>`). A 406 on a known route means the cache is poisoned, not that the route is wrong. Unknown params are ignored, so the busted URL returns the same data.
3. **Verify a new sub-route by response size.** An unknown sub-path returns the *parent* resource with status 200 (`matches/1/events/` returns match 1). If the body is byte-identical to the parent, the route does not exist.
4. **Paths end with `/`.** `stages/1` redirects with a 302; query strings go after the slash: `stages/1/matches/?round=3`.

## Data model

```
country ─┬─ tournament            Eliteserien, NM cup, Premier League   (a competition, no year)
         │    └─ stage            Eliteserien 2026, CL 2025/26 Gruppe A (a season or group; holds matches + table)
         │         ├─ table
         │         ├─ statistics  aggregate goals/cards/results for the stage
         │         └─ match ─┬─ result          homeScore45/90/105/120, ...Penalties
         │                   ├─ homeTeam/awayTeam  lineup (persons), formation, headCoaches, matchStatistics (incl. xg)
         │                   ├─ matchEvents     goals, cards, subs, VAR, live text comments
         │                   └─ referees, stadium, attendance, liveFeeds, matchStreams
         ├─ team ── persons (squad + staff), stages
         └─ stadium
person ── teams (career), transfers, stageStatistics (per-season apps/goals/cards/minutes)
```

Every object carries `type` (`nifs:match`), `id` (integer), `uid` (prefixed, `m_2713744`), `uuid`. List items are *compact* variants (`nifs:teamCompact`); fetch the object's own route for the full version. `externalIds` holds NFF/FIKS, Enetpulse and TV 2 ids. `sportId` 1 = football (the API also lists hockey, handball, bandy, but routes here were only verified for football).

## Routes

| Route | Returns | Notes |
|---|---|---|
| `countries/` | 282 countries, confederations, placeholders | `?hasTeams=1`, `?hasTournaments=1`. Norway = `1`, England = `2`, Sverige = `5`, UEFA = `14`, FIFA = `4` |
| `countries/{id}/` | country | |
| `countries/{id}/tournaments/` | tournaments in country | `?inCustomerStages=1&withStagesAndTeams=1` embeds each tournament's current stage but drops tournaments without one (Norway: 89 → 53) |
| `countries/{id}/teams/` | teamCompact list | includes youth/women/reserve teams |
| `countries/{id}/stadiums/` | stadiums | Norway is ~2 MB |
| `countries/{id}/municipalities/` | municipalities with county | |
| `tournaments/` | every tournament | ~700 KB |
| `tournaments/{id}/` | tournament | |
| `tournaments/{id}/stages/` | all stages, newest first | `[0]` is the current season |
| `stages/{id}/` | stage | `numberOfRounds`, `active`, `data` flags say which stats exist |
| `stages/{id}/matches/` | match list (no events/lineups) | `?round=N`, `?teamId=N` both filter |
| `stages/{id}/table/` | table | see Tables below |
| `stages/{id}/teams/` | teamCompact list | |
| `stages/{id}/statistics/` | stage aggregates | result distribution, biggest wins, cards per team |
| `matches/{id}/` | full match | ~175 KB with live text |
| `matches/?date=YYYY-MM-DD` | every match worldwide that day | **unfilterable**, 1–2k matches, 2–5 MB. See Recipes |
| `teams/{id}/` | full team | `players`, `staff`, `stadiums`, `kits`, `honours`, `names` |
| `teams/{id}/persons/` | squad with `shirtNumber`, `position`, `fromDate`/`toDate`, `active` | |
| `teams/{id}/stages/` | every stage the team has played in | |
| `persons/{id}/` | full person | `teams` (career), `transfers`, `stageStatistics`, `profilePicture` |
| `persons/?search=TERM` | name search | multi-word queries narrow results; returns compact persons |
| `teams/?search=TERM` | name search | returns every variant (`Molde`, `Molde 2`, women, youth); filter on `gender`, `isYouthTeam` |
| `stadiums/?search=TERM`, `stadiums/{id}/` | stadium | capacity, pitch size, surface |
| `sports/` | sport list | |
| `<schema>.json` | JSON Schema | see Schemas below |

Routes verified absent: `teams/{id}/matches/`, `persons/{id}/matches/`, `players/`, `referees/`, `search/`, `tournaments/?search=` (ignores the param), any top-scorer route.

Images are served from `https://api.nifs.no/images/...`; use the `url` field on any `nifs:image` object.

## Known ids

| Thing | id |
|---|---|
| Eliteserien (tournament) | `5` |
| Eliteserien 2026 (stage) | `700911` |
| Eliteserien 2025 (stage) | `697979` |
| Molde | `6` |
| Bodø/Glimt | `8` |
| Aalesund | `46` |

Other ids: resolve through `countries/1/tournaments/`, `tournaments/{id}/stages/`, or `?search=`.

## Recipes

**Current table**: `tournaments/5/stages/` → `[0].id` → `stages/{id}/table/`. Each row in `teams[]` has `place`, `played`, `won`, `draw`, `lost`, `goalsScored`, `goalsConceded`, `goalDifference`, `points`, `lastSixMatches` (comma list of `resultId`: 1 won, 2 lost, 3 draw), `changeSinceLastRound`, `shortName`, `logo`. `tableDividingLines[]` marks promotion/relegation zones (`fromPlace`, `toPlace`, `typeId`). `stage.comment` explains the zones in Norwegian.

**Fixtures and results for a league**: `stages/{id}/matches/` and filter client-side by `matchStatusId` and `timestamp`. Cheaper than the date route by orders of magnitude.

**A team's matches**: `stages/{id}/matches/?teamId={teamId}` per stage; get the stages from `teams/{id}/stages/`.

**Matches on a date**: `matches/?date=` returns the whole world. Filter client-side on `tournamentId` / `stageId`; cache the result server-side and never fetch it from a browser.

**Match report**: `matches/{id}/`. Group `matchEvents` by `sorting`: events sharing a `sorting` belong together (goal + assist, substituted + substitute on, penalty + penalty goal). Order by `periodSorting`, then `sorting`. Use `timeRounded` (+ `overtimeRounded` for stoppage time) as the display minute. Show lineups only when `isLineupConfirmed` is true.

**Live match**: poll `matches/{id}/` no faster than the 30 min cache allows unless you cache-bust; `lastUpdated` changes whenever anything in the match changes. `timeStartFirstHalf` / `timeStartSecondHalf` let you compute the running clock.

**Linking Norsk Tipping coupons**: NIFS has no Norsk Tipping or Betradar ids; see [`norsk-tipping-api.md`](norsk-tipping-api.md).

**Player season stats / top scorers**: there is no stage-level player-stats route. Per-person numbers are in `persons/{id}/`.`stageStatistics[]` (`matches`, `goals`, `minutes`, `yellowCards`, `redCards`, ...). For a stage-wide top-scorer list, aggregate goal events (`matchEventTypeId` 2, 10) across `matches/{id}/` for every played match in the stage.

## Codes

The full code lists live in the schemas (`matches.json`, `matchEvent.json`). The common ones:

`matchStatusId`: 1 played · 2 not started · 3 postponed · 4 abandoned · 5 will not be played · 6 date not set · 7 ongoing · 8 first half · 9 half time · 10 second half · 11–15 extra time / penalties · 16 played but cancelled · 17 played, not counted in statistics.
Live = 7–15. Finished = 1.

`matchEventTypeId`: 1 comment (live text) · 2 goal · 3 red card · 4 yellow card · 5 assist · 6 offside · 8 own goal (attached to the team that conceded) · 9 penalty · 10 penalty goal · 11 penalty miss · 12 second yellow · 13 disallowed goal · 14 kick-off · 15 half time · 16 match ends · 23 player substituted · 24 substitute on · 25 corner · 26 second half starts · 43 lineup ready · 48 indirect assist · 123 VAR · 126 injury time (`comment` holds added minutes) · 130 penalty save.

`periodId`: 1 before match · 2 first half · 3 half time · 4 second half · 5–8 extra time · 30 penalties · 31 after match.

`matchTypeId`: null regular match (use `round`) · 1 final · 2 bronze final · 3 semi final · 4 quarter final · 5 round of 16 · 25 round of 32.

`refereeTypeId`: 1 referee · 2 assistant · 4 fourth official · 6 VAR.

Team `resultId`: 1 won · 2 lost · 3 draw. `resultTypeId`: 1 after 90 · 2 after extra time · 3 on penalties.

`stageTypeId`: 1 league · 2 cup. `tournamentTypeId`: 1 national team · 2 club · 3 international club (CL) · 4/5/6 friendlies · 7 youth.

`position.id`: 1 keeper · 2 defender · 6 midfield · 10 striker (3–5, 7–9 are specific roles). `x`/`y` place a player on a 7×7 grid: `y` 1 keeper → 7 forwards, `x` 1 right → 7 left.

## Schemas

JSON Schema (draft-04) files served at the root: `matches.json`, `matchEvent.json`, `stages.json`, `table.json`, `tournaments.json`, `countries.json`, `teamInMatch.json`, `personsInMatch.json`, `teamInMatchStatistics.json`, `refereeInMatch.json`, `matchRelation.json`, `liveFeed.json`, `championships.json`, `position.json`, `image.json`, `video.json`, `user.json`, `municipalities.json`, `sports.json`, plus `*Compact.json` variants. Appending `?help=1` to most list/detail routes returns the matching schema.

The schemas are older than the API: live responses carry fields they omit (`xg`, `headCoaches`, `transferWindow*`, `tournamentId`). Trust a real response over a schema; use the schemas for code meanings.
