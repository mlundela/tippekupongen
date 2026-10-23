# Norsk Tipping API reference and NIFS join

Norsk Tipping's pool-game (Tipping) coupons: the 12 matches per coupon, expert and public tips, turnover, prizes.
Mapped by probing on 2026-10-23. NIFS routes and request rules are in [`nifs-api.md`](nifs-api.md).

## Endpoint

`GET https://api.norsk-tipping.no/PoolGamesSportInfo/v1/api/tipping/live-info`

No auth, CORS `*`, ~33 KB. Works without an `Accept` header. Returns only the *currently open* coupons, so anything you need later must be stored when you see it.

```
gameDays[]                 one per coupon: dayType SATURDAY | SUNDAY | MIDWEEK
  game
    status                 OPENED (other values not yet observed)
    matches[12]
      gameEngineEventId    NT match id
      gameEngineBetRadarId Betradar match id (NIFS has no Betradar ids)
      gameEngineSortingNumber  1–12, coupon line
      name                 "HamKam - Rosenborg"
      date                 kickoff, ISO 8601 with offset
      arrangement {id, name}   NT competition: "NOR Eliteserien"
      teams.home|away {id, webName, mobileName, retailerName, acronymName, teletextName}
      status {value, description.mainText}   NOT_STARTED observed
      results, withdraws{fullTime, halfTime}, broadcasts[]
    tips.fullTime|halfTime.expert|peoples[12]   {home, draw, away} in percent; no match key: they follow matches[] order (checked against match strength on 2026-10-23)
    sales.fullTime|halfTime {saleStopDate, saleAmount{amount, currency}}
    prizes.fullTime|halfTime.tenGroup|elevenGroup|twelveGroup
probability, bonuspot      coupon-level text
```

Name fields: `webName` is the full name (`Queens PR`, `Manchester United`); `acronymName` and `teletextName` are 7-char abbreviations (`Kr.sund`). Match on `webName`, `mobileName` and `retailerName`.

## Joining with NIFS

The two APIs share **no ids**: NT has its own team, competition and match ids plus Betradar; NIFS `externalIds` hold only FIKS, Enetpulse and TV 2. Matching ids are coincidence (Eliteserien is `5` in both; Premier League is NT `1`, NIFS `7`).

The join key is the **match**: same kickoff instant + matching team names. Each joined match yields two NT→NIFS team-id pairs, which go into the team map.

### Team map

[`data/nt-nifs-teams.json`](../data/nt-nifs-teams.json) is the single source of truth: one row per team, `{ntTeamId, ntName, nifsTeamId, nifsName, source, verifiedOn}`. `source` is `auto` (from the join below) or `manual` (a hand-fixed row; the join never overwrites these).

To join an NT team: look up `ntTeamId` in the map. On a miss, run the match join, then append the new pairs.

### Match join

For each NT match:

1. Fetch NIFS matches for the kickoff's date (see Competitions below for the cheap route). Keep the NIFS matches whose `timestamp` is the same instant as NT `date` (compare as parsed datetimes; the offsets match in practice, but parsed comparison is the safe one).
2. Score each candidate: normalise both names (lowercase, strip accents to ASCII, drop the tokens `fc afc fk if il sk bk cf`, collapse non-alphanumerics to spaces). Exact = 1.0, one contains the other = 0.9, else `difflib.SequenceMatcher` ratio. Candidate score = min(home score, away score), taking each side's best over `webName`/`mobileName`/`retailerName`.
3. Accept the best candidate at ≥ 0.6. Log every miss with its candidate count; a miss usually means the kickoff time differs between the two APIs.

Result on 2026-10-23: **36/36 matches joined, 55 teams, no conflicts** (no NT id mapped to two NIFS ids). The only fuzzy hit was `Queens PR` → `Queens Park Rangers` at 0.64, just above the threshold. Treat any hit below 0.9 as one to eyeball, and watch for reserve and women's teams (`Molde 2`) when widening the search.

### Competitions

Fetching `matches/?date=` from NIFS costs 2–5 MB per day. When the NT competition is known, fetch the NIFS stage's matches instead (`stages/{stageId}/matches/`, filter by kickoff).

[`data/nt-nifs-arrangements.json`](../data/nt-nifs-arrangements.json) maps NT `arrangement.id` → NIFS tournament id. The current stage is NIFS `tournaments/{id}/stages/` `[0]` (verified for all six mapped tournaments on 2026-10-23). Unknown arrangements fall back to the date route. Add a row when a new arrangement shows up on a coupon.
