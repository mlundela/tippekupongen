"""Norsk Tipping Oddsen: bookmaker H/U/B odds. API and quirks: docs/oddsen-api.md."""

import json
import urllib.request
from datetime import datetime

from .join import ARRANGEMENTS, _sim

CONTENT_GET = "https://www-opr1.sport2.norsk-tipping.no/services/content/get"
REGION = "1355"
HUB_MARKET = "HUB"


def content(content_type, content_id):
    body = json.dumps({"contentId": {"type": content_type, "id": content_id},
                       "clientContext": {"language": "NO", "ipAddress": "0.0.0.0"}}).encode()
    req = urllib.request.Request(CONTENT_GET, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json", "poseidon": "oddsen"})
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.loads(r.read())
    if out.get("errorType"):
        raise LookupError(f"Oddsen {content_type} {content_id}: {out['errorType']}")
    return out["data"]


def _events_in_country(country_node):
    """All pre-match events under a country node, from every tournament that currently has events."""
    events = []
    for t in content("boNavigationList", f"{REGION}/{country_node}")["bonavigationnodes"]:
        if int(t.get("numevents") or 0) == 0:
            continue
        node = content("boNavigationList", f"{REGION}/{t['idfwbonavigation']}")
        for mg in node.get("marketgroups") or []:
            events += content("eventGroup", mg["idfwmarketgroup"]).get("events") or []
    return events


def _hub(event):
    """Decimal odds and margin-free implied percentages for the H/U/B market, or None."""
    market = next((m for m in event.get("markets") or [] if m.get("name") == HUB_MARKET), None)
    if not market:
        return None
    odds = {}
    for s in market["selections"]:
        key = {"H": "home", "D": "draw", "A": "away"}.get(s.get("hadvalue"))
        if key:
            odds[key] = round(1 + int(s["currentpriceup"]) / int(s["currentpricedown"]), 2)
    if len(odds) != 3:
        return None
    inv = {k: 1 / v for k, v in odds.items()}
    total = sum(inv.values())
    implied = {k: round(100 * v / total) for k, v in inv.items()}
    return {"odds": odds, "implied": implied, "margin": round(100 * (total - 1), 1),
            "oddsenEventId": event["idfoevent"], "oddsenName": event["name"]}


def odds_for(nt_matches):
    """{ntEventId: hub odds} for coupon matches, linked on kickoff instant + team names."""
    arrangements = {a["ntArrangementId"]: a for a in json.loads(ARRANGEMENTS.read_text())}
    pools = {}
    out = {}
    for m in nt_matches:
        country = (arrangements.get(m["arrangement"]["id"]) or {}).get("oddsenCountryNode")
        if not country:
            continue
        if country not in pools:
            pools[country] = _events_in_country(country)
        kickoff = datetime.fromisoformat(m["date"])
        home, away = m["teams"]["home"], m["teams"]["away"]
        best = max(((min(max(_sim(home[f], e["participantname_home"]) for f in ("webName", "mobileName")),
                         max(_sim(away[f], e["participantname_away"]) for f in ("webName", "mobileName"))), e)
                    for e in pools[country] if datetime.fromisoformat(e["tsstart"]) == kickoff),
                   default=(0, None), key=lambda t: t[0])
        if best[0] >= 0.6 and (hub := _hub(best[1])):
            out[m["gameEngineEventId"]] = hub
    return out
