# Norsk Tipping Oddsen reference

Bookmaker odds from Norsk Tipping's Oddsen. Mapped by reading the sportsbook bundle on 2026-10-23; there is no public documentation. Client: `altomfotball/oddsen.py`.

## Endpoint

`POST https://www-opr1.sport2.norsk-tipping.no/services/content/get` (also served at `https://www.norsk-tipping.no/sport/oddsen/sportsbook/services/content/get`). No auth.

```http
Content-Type: application/json
poseidon: oddsen

{"contentId": {"type": "<contentType>", "id": "<id>"}, "clientContext": {"language": "NO", "ipAddress": "0.0.0.0"}}
```

Response: `{"data": …, "version": …}`, or `{"errorType": "CONTENT_NOT_FOUND", …}` with status 200 on a bad id.

`api.norsk-tipping.no/OddsenGameInfo/v1/api/` is a different service. Only `sports` and `events/{id}` answer there; everything else is 403. Use the sportsbook endpoint above.

## Walking to the odds

1. `boNavigationList`, id `1355/<node>` (`1355` is the region prefix). Football root is node `42978.1`. Its `bonavigationnodes` are countries: Norge `66760.1`, England `66748.1`, Spania `66743.1`, Tyskland `66768.1`, Italia `66751.1`, Frankrike `66774.1`, Nederland `66721.1`, Portugal `66731.1`. UEFA competitions (Champions/Europa/Conference League, Nations League, EM and its qualifiers) sit under Europa `66756.1`, friendlies under Internasjonal `66765.1`, and VM 2026 under a second Internasjonal `71348.1`. Some competitions appear under more than one node; which one carries events was only checked for the Champions League (Europa, 2026-10-26).
2. A country's children are tournaments. Several nodes share a name (two «Eliteserien», two «Championship»): use the one with `numevents` > 0.
3. A tournament node's `marketgroups[].idfwmarketgroup` (type `MATCHESCOUPON`) → `eventGroup` with that id returns `events[]`.
4. Each event has `name`, `participantname_home`/`_away`, `tsstart` (ISO with offset), and `markets[]`. The 1X2 market has `name: "HUB"`. Its `selections[]` carry `hadvalue` (`H`/`D`/`A`) and fractional odds `currentpriceup`/`currentpricedown`: decimal odds = 1 + up / down.

`data/nt-nifs-arrangements.json` maps each NT arrangement to its Oddsen country node (`oddsenCountryNode`). The client pools the events of every tournament with events in that country, so it doesn't need to track which duplicate node is live.

## Joining with the coupon

Oddsen events carry no Betradar or NT ids (`externalprovider` is `SSLN` with an opaque reference). Join on the same kickoff instant plus team-name similarity (`join._sim`, ≥ 0.6), as for NIFS. Names differ in length (`KFUM` vs `KFUM Oslo`, `Tottenham Hotspur` vs `Tottenham`), and the containment rule covers that. On 2026-10-23 all 12 Saturday matches linked.

## Using the odds

Implied probability = (1/odds) ÷ Σ(1/odds), which removes the margin (≈ 6.5–7.3 % on this coupon). Odds and the public's split (`tips.fullTime.peoples`) move until sale stop, so fetch both in the same `facts` run.
