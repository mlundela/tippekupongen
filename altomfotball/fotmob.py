"""FotMob: injuries and suspensions per match. API and quirks: docs/fotmob-api.md."""

import re
import unicodedata
from datetime import datetime

from .fetch import get_json
from .join import _sim

BASE = "https://www.fotmob.com/api/data/"
TYPES = {"injury": "injury", "suspension": "suspension"}


def _day(date):
    return get_json(f"{BASE}matches?date={date.strftime('%Y%m%d')}", max_age=1800)


def _details(match_id):
    return get_json(f"{BASE}matchDetails?matchId={match_id}", max_age=1800)


def _link(kickoff, home, away):
    """FotMob match id for a fixture: same UTC kickoff, one side named near-identically (≥ 0.9) and the
    other at least loosely (≥ 0.4). FotMob uses full club names ("Hamarkameratene" for HamKam)."""
    best = (0, None)
    for league in _day(kickoff)["leagues"]:
        for m in league["matches"]:
            if datetime.fromisoformat(m["status"]["utcTime"].replace("Z", "+00:00")) != kickoff:
                continue
            sides = sorted((max(_sim(home, m["home"][k]) for k in ("name", "longName")),
                            max(_sim(away, m["away"][k]) for k in ("name", "longName"))))
            if sides[1] >= 0.9 and sides[0] >= 0.4 and sum(sides) > best[0]:
                best = (sum(sides), m["id"])
    return best[1]


def unavailable(kickoff, home, away):
    """{"home": [...], "away": [...]} of players FotMob lists as out for this match, or None if the
    match is not found. Each item: name, firstName, lastName, type (injury|suspension), expectedReturn."""
    match_id = _link(kickoff, home, away)
    if not match_id:
        return None
    lineup = _details(match_id).get("content", {}).get("lineup") or {}
    out = {"fotmobMatchId": match_id}
    for side, key in (("home", "homeTeam"), ("away", "awayTeam")):
        out[side] = [{
            "name": p["name"], "firstName": p.get("firstName"), "lastName": p.get("lastName"),
            "type": TYPES.get((p.get("unavailability") or {}).get("type"), "other"),
            "expectedReturn": (p.get("unavailability") or {}).get("expectedReturn"),
        } for p in (lineup.get(key) or {}).get("unavailable") or []]
    return out


def _tokens(name):
    s = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()
    return [t for t in re.split(r"[^a-z]+", s) if t]


def _exact(fotmob_player, nifs_name):
    a, b = set(_tokens(fotmob_player["name"])), set(_tokens(nifs_name))
    return a == b or bool(a and b and (a <= b or b <= a) and min(len(a), len(b)) >= 2)


def _loose(fotmob_player, nifs_name):
    last = _tokens(fotmob_player.get("lastName") or fotmob_player["name"])
    first = _tokens(fotmob_player.get("firstName") or "")
    nifs = _tokens(nifs_name)
    return bool(last and nifs and last[-1] == nifs[-1] and (not first or first[0][0] == nifs[0][0]))


def match_players(fotmob_players, nifs_players):
    """{index in fotmob_players: nifs player}. Names differ in order, accents and nicknames
    ("Paik Seung-Ho" vs "Seung-ho Paik"). Exact token matches first; surname + initial only when it
    picks out exactly one remaining player (two "B. Traoré" at Wolves)."""
    out, taken = {}, set()
    for i, f in enumerate(fotmob_players):
        hits = [p for p in nifs_players if _exact(f, p["name"])]
        if len(hits) == 1:
            out[i] = hits[0]
            taken.add(hits[0]["id"])
    for i, f in enumerate(fotmob_players):
        if i in out:
            continue
        hits = [p for p in nifs_players if p["id"] not in taken and _loose(f, p["name"])]
        if len(hits) == 1:
            out[i] = hits[0]
            taken.add(hits[0]["id"])
    return out


def _stat(details, title):
    for group in ((details.get("content") or {}).get("stats") or {}).get("Periods", {}).get("All", {}).get("stats", []):
        for s in group.get("stats") or []:
            if s.get("title") == title and s.get("stats"):
                return s["stats"]
    return None


def match_report(kickoff, home, away):
    """Facts for a short recap of a finished match, or None if FotMob doesn't have it."""
    match_id = _link(kickoff, home, away)
    if not match_id:
        return None
    d = _details(match_id)
    general, facts = d.get("general") or {}, (d.get("content") or {}).get("matchFacts") or {}
    events = (facts.get("events") or {}).get("events") or []
    goals = [{"minute": e.get("time"), "added": e.get("overloadTime"), "name": e.get("nameStr"),
              "side": "home" if e.get("isHome") else "away", "ownGoal": bool(e.get("ownGoal")),
              "penalty": (e.get("goalDescriptionKey") or "") == "penalty" or "Penalty" in (e.get("goalDescription") or "")}
             for e in events if e.get("type") == "Goal"]
    reds = [{"minute": e.get("time"), "name": e.get("nameStr"), "side": "home" if e.get("isHome") else "away",
             "card": e.get("card")} for e in events if e.get("type") == "Card" and e.get("card") in ("Red", "YellowRed")]
    potm = facts.get("playerOfTheMatch") or {}
    header = (d.get("header") or {}).get("teams") or []
    return {
        "fotmobMatchId": match_id,
        "competition": (facts.get("infoBox") or {}).get("Tournament", {}).get("leagueName"),
        "home": (general.get("homeTeam") or {}).get("name"), "away": (general.get("awayTeam") or {}).get("name"),
        "score": [t.get("score") for t in header] if len(header) == 2 else None,
        "goals": goals, "reds": reds,
        "xg": _stat(d, "Expected goals (xG)"), "shots": _stat(d, "Total shots"),
        "shotsOnTarget": _stat(d, "Shots on target"), "bigChances": _stat(d, "Big chances"),
        "possession": _stat(d, "Ball possession"),
        "playerOfTheMatch": {"name": (potm.get("name") or {}).get("fullName"), "team": potm.get("teamName"),
                             "rating": (potm.get("rating") or {}).get("num")} if potm else None,
        "highlights": (facts.get("highlights") or {}).get("url"),
    }
