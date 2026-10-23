"""Per-match fact sheets for a Norsk Tipping coupon, computed from NIFS data.

Event rules (verified against Eliteserien 2026 results):
- A goal is a type 2 or 8 event that carries `score`; the side whose score went up scored.
- Type 10 (penalty goal) carries no score: it marks the scorer's next goal as a penalty.
"""

from collections import defaultdict
from datetime import datetime, timedelta

from . import nifs

GOAL, OWN_GOAL, PENALTY_GOAL, ASSIST = 2, 8, 10, 5
YELLOW, RED, SECOND_YELLOW = 4, 3, 12
BUCKETS = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90")

# Yellow-card counts that trigger a one-match league ban, per NIFS tournament id.
# Eliteserien: 3rd yellow, then every 2nd (NFF). England: 5th, 10th, 15th (thresholds apply this early in the season).
BAN_THRESHOLDS = {
    5: lambda n: n >= 3 and n % 2 == 1,
    7: lambda n: n in (5, 10, 15),
    28: lambda n: n in (5, 10, 15),
}


def _ts(m):
    return datetime.fromisoformat(m["timestamp"])


def _played_before(matches, kickoff):
    return sorted((m for m in matches if m["matchStatusId"] == nifs.PLAYED and _ts(m) < kickoff), key=_ts)


def _result(m, team_id):
    home = m["homeTeam"]["id"] == team_id
    r = m["result"]
    gf, ga = (r["homeScore90"], r["awayScore90"]) if home else (r["awayScore90"], r["homeScore90"])
    if r.get("homeScore120") is not None:
        gf, ga = (r["homeScore120"], r["awayScore120"]) if home else (r["awayScore120"], r["homeScore120"])
    pens = None
    if r.get("homeScorePenalties") is not None:
        pens = (r["homeScorePenalties"], r["awayScorePenalties"]) if home else (r["awayScorePenalties"], r["homeScorePenalties"])
    outcome = "V" if gf > ga else "T" if gf < ga else "U"
    if pens:
        outcome = "V" if pens[0] > pens[1] else "T"
    return {
        "matchId": m["id"], "date": m["timestamp"][:10], "home": home,
        "opponent": (m["awayTeam"] if home else m["homeTeam"])["name"],
        "gf": gf, "ga": ga, "pens": pens, "outcome": outcome,
    }


def _record(results):
    rec = {"p": len(results), "v": 0, "u": 0, "t": 0, "gf": 0, "ga": 0}
    for r in results:
        rec[r["outcome"].lower()] += 1
        rec["gf"] += r["gf"]
        rec["ga"] += r["ga"]
    rec["pts"] = rec["v"] * 3 + rec["u"]
    rec["ppg"] = round(rec["pts"] / rec["p"], 2) if rec["p"] else None
    return rec


def _streak(results):
    """Current run, newest first: unbeaten / winless / wins / losses."""
    out = {}
    for name, test in (("ubeseiret", lambda o: o != "T"), ("uten_seier", lambda o: o != "V"),
                       ("seire", lambda o: o == "V"), ("tap", lambda o: o == "T")):
        n = 0
        for r in reversed(results):
            if not test(r["outcome"]):
                break
            n += 1
        out[name] = n
    return out


def _minute(e):
    """Match minute. timeRounded is absent in stoppage time and for sources without seconds,
    where `time` already is the minute."""
    if e.get("timeRounded") is not None:
        return e["timeRounded"]
    t = e.get("time")
    if t is None:
        return None
    return t + 1 if e.get("seconds") is not None and not e.get("overtime") else t


def _bucket(e):
    minute = min(_minute(e) or 0, 90)
    if e["periodId"] == 2:
        minute = min(minute, 45)
    elif e["periodId"] == 4:
        minute = max(minute, 46)
    else:
        return None
    return BUCKETS[min((max(minute, 1) - 1) // 15, 5)]


def _goals(detail):
    """Goals in order: {side: 'home'|'away', minute, bucket, personId, name, penalty, ownGoal}."""
    events = sorted(detail["matchEvents"], key=lambda e: (e["periodSorting"], e["sorting"]))
    pending_pen = set()
    prev = (0, 0)
    goals = []
    for e in events:
        t = e["matchEventTypeId"]
        pid = (e.get("person") or {}).get("id")
        if t == PENALTY_GOAL and pid:
            pending_pen.add(pid)
        if t not in (GOAL, OWN_GOAL) or not e.get("score"):
            continue
        h, a = (int(x) for x in e["score"].split("-"))
        side = "home" if h > prev[0] else "away"
        prev = (h, a)
        goals.append({
            "side": side, "minute": _minute(e), "bucket": _bucket(e), "periodId": e["periodId"],
            "personId": pid, "name": (e.get("person") or {}).get("name"),
            "penalty": pid in pending_pen and t == GOAL, "ownGoal": t == OWN_GOAL,
        })
        pending_pen.discard(pid)
    return goals


FRIENDLY_TYPES = {4, 5, 6}  # tournamentTypeId: club, national-team and training friendlies


def _tournament(tournament_id):
    """Full tournament; stage objects only embed a compact one without type or category."""
    return nifs.get(f"tournaments/{tournament_id}/", max_age=24 * 3600)


def _is_league(stage):
    t = _tournament(stage["tournament"]["id"])
    return stage["stageTypeId"] == 1 and t["tournamentTypeId"] == 2 and t["tournamentCategoryId"] == 1


def _league_stage(team_id, match_stage, kickoff):
    """The national league the team plays this season. Country is no test: Welsh clubs play in English leagues."""
    if _is_league(match_stage):
        return match_stage
    for s in nifs.team_stages(team_id):
        end = datetime.fromisoformat(s["dateEnd"]) if s.get("dateEnd") else None
        if end and end.date() >= kickoff.date() and _is_league(s):
            return nifs.get(f"stages/{s['id']}/", max_age=6 * 3600)
    return None


def _all_competitions_form(team_id, kickoff, n=6):
    since = kickoff - timedelta(days=150)
    pool = []
    for s in nifs.team_stages(team_id):
        end = s.get("dateEnd")
        if end and datetime.fromisoformat(end) >= since and _tournament(s["tournament"]["id"])["tournamentTypeId"] not in FRIENDLY_TYPES:
            for m in _played_before(nifs.stage_matches(s["id"], team_id), kickoff):
                if _ts(m) >= since:
                    pool.append((m, s["fullName"]))
    pool.sort(key=lambda t: _ts(t[0]))
    return [dict(_result(m, team_id), competition=name) for m, name in pool[-n:]]


def team_facts(team_id, kickoff, match_stage):
    team = nifs.get(f"teams/{team_id}/", max_age=6 * 3600)
    league = _league_stage(team_id, match_stage, kickoff)
    facts = {"id": team_id, "name": team["name"], "logo": (team.get("logo") or {}).get("url"),
             "form": _all_competitions_form(team_id, kickoff)}
    if not league:
        return facts

    played = _played_before(nifs.stage_matches(league["id"], team_id), kickoff)
    details = nifs.matches([m["id"] for m in played])
    results = [_result(m, team_id) for m in played]

    table = nifs.stage_table(league["id"])
    rows = table["teams"]
    row = next((r for r in rows if r["id"] == team_id), None)
    if row:
        facts["table"] = {
            "place": row["place"], "of": len(rows), "points": row["points"], "played": row["played"],
            "gf": row["goalsScored"], "ga": row["goalsConceded"], "gd": row["goalDifference"],
            "attackRank": 1 + sum(r["goalsScored"] > row["goalsScored"] for r in rows),
            "defenceRank": 1 + sum(r["goalsConceded"] < row["goalsConceded"] for r in rows),
            "leaderPoints": rows[0]["points"],
        }

    facts["league"] = {"stageId": league["id"], "name": league["fullName"], "tournamentId": league["tournament"]["id"]}
    facts["overall"] = _record(results)
    facts["homeRecord"] = _record([r for r in results if r["home"]])
    facts["awayRecord"] = _record([r for r in results if not r["home"]])
    facts["last6League"] = results[-6:]
    facts["streak"] = _streak(results)
    facts["cleanSheets"] = sum(r["ga"] == 0 for r in results)
    facts["failedToScore"] = sum(r["gf"] == 0 for r in results)

    scored_b = dict.fromkeys(BUCKETS, 0)
    conceded_b = dict.fromkeys(BUCKETS, 0)
    halves = {"1": [0, 0], "2": [0, 0]}  # [scored, conceded]
    led_not_won = came_from_behind = 0
    stats = defaultdict(list)
    players = {}

    def player(p):
        pid = p["id"] if "personId" not in p else p["personId"]
        return players.setdefault(pid, {
            "id": pid, "name": p["name"], "apps": 0, "starts": 0, "minutes": 0, "goals": 0, "penalties": 0,
            "assists": 0, "yellows": 0, "reds": 0, "ratings": [], "log": []})

    for m, d, r in zip(played, details, results):
        my_side = "home" if r["home"] else "away"
        lead = trail = False
        h = a = 0
        for g in _goals(d):
            mine = g["side"] == my_side
            if g["bucket"]:
                (scored_b if mine else conceded_b)[g["bucket"]] += 1
            if g["periodId"] in (2, 4):
                halves["1" if g["periodId"] == 2 else "2"][0 if mine else 1] += 1
            h, a = (h + (g["side"] == "home"), a + (g["side"] == "away"))
            us, them = (h, a) if r["home"] else (a, h)
            lead |= us > them
            trail |= us < them
            if mine and not g["ownGoal"] and g["personId"]:
                pl = players.get(g["personId"])
                if pl is None:
                    pl = player({"personId": g["personId"], "name": g["name"]})
                pl["goals"] += 1
                pl["penalties"] += g["penalty"]
                pl["log"].append((m["timestamp"][:10], "goal"))
        led_not_won += lead and r["outcome"] != "V"
        came_from_behind += trail and r["outcome"] == "V"

        me = d[f"{my_side}Team"]
        for k in ("xg", "totalShots", "shotsOnGoal", "possession", "corners"):
            v = (me.get("matchStatistics") or {}).get(k)
            if v is not None:
                stats[k].append(v)
        opp = d["awayTeam" if r["home"] else "homeTeam"]
        for k in ("xg", "totalShots", "shotsOnGoal"):
            v = (opp.get("matchStatistics") or {}).get(k)
            if v is not None:
                stats[f"{k}Against"].append(v)

        for p in me.get("persons") or []:
            pl = player(p)
            if p.get("startsMatch") or p.get("entersFieldMinute") is not None:
                pl["apps"] += 1
            pl["starts"] += bool(p.get("startsMatch"))
            pl["minutes"] += p.get("minutesPlayed") or 0
            if p.get("rating"):
                pl["ratings"].append(p["rating"])
            pl["log"].append((m["timestamp"][:10], "squad"))
        for e in d["matchEvents"]:
            t = e["matchEventTypeId"]
            if (e.get("team") or {}).get("id") != team_id or not e.get("person"):
                continue
            if t in (ASSIST, YELLOW, RED, SECOND_YELLOW):
                pl = player({"personId": e["person"]["id"], "name": e["person"]["name"]})
                key = {ASSIST: "assist", YELLOW: "yellow", RED: "red", SECOND_YELLOW: "red"}[t]
                if t == ASSIST:
                    pl["assists"] += 1
                elif t == YELLOW:
                    pl["yellows"] += 1
                else:
                    pl["reds"] += 1
                pl["log"].append((m["timestamp"][:10], key))
                if t == SECOND_YELLOW:
                    pl["log"].append((m["timestamp"][:10], "second_yellow"))

    facts["goalTiming"] = {"scored": scored_b, "conceded": conceded_b,
                           "firstHalf": halves["1"], "secondHalf": halves["2"]}
    facts["ledNotWon"] = led_not_won
    facts["cameFromBehind"] = came_from_behind
    facts["averages"] = {k: round(sum(v) / len(v), 2) for k, v in stats.items() if v}
    facts["underlying"] = _underlying(stats, facts["overall"])
    if row:
        facts["table"]["withdrawnPoints"] = row.get("withdrawnPoints") or 0
    facts["restDays"] = (kickoff.date() - datetime.fromisoformat(facts["form"][-1]["date"]).date()).days if facts["form"] else None
    facts["coach"] = next((c["name"] for c in (details[-1][("home" if results[-1]["home"] else "away") + "Team"].get("headCoaches") or [])), None) if details else None

    last5 = {m["timestamp"][:10] for m in played[-5:]}
    for pl in players.values():
        pl["last5Goals"] = sum(1 for d, k in pl["log"] if k == "goal" and d in last5)
        pl["last5Assists"] = sum(1 for d, k in pl["log"] if k == "assist" and d in last5)
        recent = [r for r in pl["ratings"][-5:]]
        pl["avgRating"] = round(sum(pl["ratings"]) / len(pl["ratings"]), 2) if pl["ratings"] else None
        pl["avgRatingLast5"] = round(sum(recent) / len(recent), 2) if recent else None

    ranked = sorted(players.values(), key=lambda p: (p["goals"] + p["assists"], p["goals"]), reverse=True)
    facts["topContributors"] = [_public(p) for p in ranked[:5] if p["goals"] + p["assists"] > 0]
    facts["inForm"] = [_public(p) for p in sorted(
        players.values(), key=lambda p: (p["last5Goals"] + p["last5Assists"], p["last5Goals"], p["avgRatingLast5"] or 0),
        reverse=True)[:4] if p["last5Goals"] + p["last5Assists"] > 0]
    rated = [p for p in players.values() if p["avgRating"] and len(p["ratings"]) >= 5]
    facts["bestRated"] = [_public(p) for p in sorted(rated, key=lambda p: p["avgRatingLast5"], reverse=True)[:3]]
    facts["absences"] = _absences(players, played, league, kickoff, match_stage, team_id)
    facts["players"] = _player_cards(players, facts["absences"], team_id, facts["overall"]["gf"])
    return facts


def _underlying(stats, overall):
    """Quality vs luck. xG and shot totals only when every league match has them.
    PDO = goals per shot on target + share of opponents' shots on target saved; ~1.00 is neutral,
    far from it usually regresses."""
    n = overall["p"]
    out = {"matches": n}
    if n and len(stats["xg"]) == n and len(stats["xgAgainst"]) == n:
        out["xg"], out["xgAgainst"] = round(sum(stats["xg"]), 1), round(sum(stats["xgAgainst"]), 1)
        out["goalsMinusXg"] = round(overall["gf"] - out["xg"], 1)
        out["concededMinusXga"] = round(overall["ga"] - out["xgAgainst"], 1)
    if n and len(stats["shotsOnGoal"]) == n and len(stats["shotsOnGoalAgainst"]) == n:
        sot, sota = sum(stats["shotsOnGoal"]), sum(stats["shotsOnGoalAgainst"])
        out["shotsPerMatch"] = round(sum(stats["totalShots"]) / n, 1) if len(stats["totalShots"]) == n else None
        out["shotsAgainstPerMatch"] = round(sum(stats["totalShotsAgainst"]) / n, 1) if len(stats["totalShotsAgainst"]) == n else None
        out["sotPerMatch"], out["sotAgainstPerMatch"] = round(sot / n, 1), round(sota / n, 1)
        if sot and sota:
            out["conversion"] = round(overall["gf"] / sot, 2)
            out["savePct"] = round(1 - overall["ga"] / sota, 2)
            out["pdo"] = round(out["conversion"] + out["savePct"], 2)
    return out


def _public(p):
    return {k: p[k] for k in ("id", "name", "apps", "starts", "minutes", "goals", "penalties", "assists",
                              "last5Goals", "last5Assists", "yellows", "reds", "avgRating", "avgRatingLast5")}


def _player_cards(players, absences, team_id, team_goals):
    """League stats for every player who has played, for the key-player boxes on the page."""
    squad = {p["id"]: p for p in nifs.get(f"teams/{team_id}/persons/", max_age=6 * 3600)}
    severity = ("suspended", "missing", "returning", "card_risk")
    status = {}
    for a in sorted(absences, key=lambda a: severity.index(a["kind"])):
        status.setdefault(a["id"], {"kind": a["kind"], "reason": a["reason"]})
    cards = []
    for p in players.values():
        if not p["apps"] and p["id"] not in status:
            continue
        s = squad.get(p["id"]) or {}
        cards.append({**_public(p),
                      "position": (s.get("position") or {}).get("position"),
                      "shirtNumber": s.get("shirtNumber"),
                      "goalShare": round(p["goals"] / team_goals, 2) if team_goals else None,
                      "status": status.get(p["id"])})
    return sorted(cards, key=lambda c: (c["goals"] + c["assists"], c["minutes"]), reverse=True)


def _absences(players, played, league, kickoff, match_stage, team_id):
    """Likely absences inferred from cards and squad lists. NIFS has no injury or suspension data."""
    if not played:
        return []
    is_league_match = match_stage["id"] == league["id"]
    last, prev = played[-1]["timestamp"][:10], (played[-2]["timestamp"][:10] if len(played) > 1 else None)
    ban = BAN_THRESHOLDS.get(league["tournament"]["id"])
    squad = {p["id"]: p for p in nifs.get(f"teams/{team_id}/persons/", max_age=6 * 3600)}
    out = []
    n_matches = len(played)
    for pl in players.values():
        log = pl["log"]
        in_last = any(d == last and k == "squad" for d, k in log)
        in_prev = prev and any(d == prev and k == "squad" for d, k in log)
        still_here = pl["id"] in squad and squad[pl["id"]].get("active", True)
        if is_league_match:
            if any(d == last and k == "red" for d, k in log):
                out.append({**_public(pl), "kind": "suspended", "reason": "rødt kort i forrige seriekamp"})
                continue
            # Yellows that became a red (second yellow) count toward the red, not the accumulation.
            sent_off = {d for d, k in log if k == "second_yellow"}
            yellows_upto_last = sum(1 for d, k in log if k == "yellow" and d not in sent_off)
            got_yellow_last = any(d == last and k == "yellow" for d, k in log)
            if ban and got_yellow_last and ban(yellows_upto_last):
                out.append({**_public(pl), "kind": "suspended",
                            "reason": f"{yellows_upto_last}. gule kort i forrige seriekamp"})
                continue
            # Only regulars: in Eliteserien every player on 2 or 4 yellows is one away, which is noise.
            if ban and ban(yellows_upto_last + 1) and pl["starts"] >= 0.4 * n_matches:
                out.append({**_public(pl), "kind": "card_risk",
                            "reason": f"{yellows_upto_last} gule kort – ett til gir karantene"})
            if any(d == prev and k == "red" for d, k in log) and not in_last:
                out.append({**_public(pl), "kind": "returning", "reason": "tilbake etter karantene (rødt kort)"})
                continue
        regular = pl["starts"] >= max(4, 0.5 * n_matches)
        if regular and not in_last and still_here:
            out.append({**_public(pl), "kind": "missing",
                        "reason": "ute av troppen de to siste kampene" if not in_prev else "ikke i troppen i forrige kamp"})
    return out


def head_to_head(home_id, away_id, kickoff, n=6, max_stages=14):
    away_stages = {s["id"] for s in nifs.team_stages(away_id)}
    common = [s for s in nifs.team_stages(home_id) if s["id"] in away_stages
              and _tournament(s["tournament"]["id"])["tournamentTypeId"] not in FRIENDLY_TYPES]
    common.sort(key=lambda s: s.get("dateStart") or "", reverse=True)
    meetings = []
    for s in common[:max_stages]:
        for m in _played_before(nifs.stage_matches(s["id"], home_id), kickoff):
            if away_id in (m["homeTeam"]["id"], m["awayTeam"]["id"]):
                meetings.append(dict(_result(m, home_id), competition=s["fullName"]))
        if len(meetings) >= n:
            break
    meetings.sort(key=lambda r: r["date"])
    meetings = meetings[-n:]
    return {"meetings": meetings, "record": _record(meetings),
            "atThisVenue": _record([r for r in meetings if r["home"]])}


def match_facts(nt_match, nifs_match):
    kickoff = datetime.fromisoformat(nifs_match["timestamp"])
    stage = nifs.get(f"stages/{nifs_match['stageId']}/", max_age=6 * 3600)
    home_id, away_id = nifs_match["homeTeam"]["id"], nifs_match["awayTeam"]["id"]
    return {
        "nt": {"eventId": nt_match["gameEngineEventId"], "line": nt_match["gameEngineSortingNumber"],
               "name": nt_match["name"], "arrangement": nt_match["arrangement"]["name"], "tips": nt_match["tips"]},
        "nifsMatchId": nifs_match["id"],
        "kickoff": nifs_match["timestamp"],
        "competition": stage["fullName"],
        "round": nifs_match.get("round"),
        "stadium": (nifs_match.get("stadium") or {}).get("name"),
        "home": team_facts(home_id, kickoff, stage),
        "away": team_facts(away_id, kickoff, stage),
        "h2h": head_to_head(home_id, away_id, kickoff),
    }
