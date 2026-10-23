"""Link Norsk Tipping matches to NIFS matches. Method: docs/norsk-tipping-api.md#joining-with-nifs."""

import difflib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

from . import nifs

DATA = Path(__file__).resolve().parent.parent / "data"
TEAM_MAP = DATA / "nt-nifs-teams.json"
ARRANGEMENTS = DATA / "nt-nifs-arrangements.json"
THRESHOLD = 0.6
NAME_FIELDS = ("webName", "mobileName", "retailerName")


def _norm(s):
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    s = re.sub(r"\b(fc|afc|fk|if|il|sk|bk|cf)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _sim(a, b):
    a, b = _norm(a), _norm(b)
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


def _side_score(nt_team, nifs_team, team_map):
    known = team_map.get(nt_team["id"])
    if known:
        return 1.0 if known["nifsTeamId"] == nifs_team["id"] else 0.0
    return max(_sim(nt_team[f], nifs_team["name"]) for f in NAME_FIELDS)


def load_team_map():
    return {r["ntTeamId"]: r for r in json.loads(TEAM_MAP.read_text())}


def save_team_map(team_map):
    rows = sorted(team_map.values(), key=lambda r: r["nifsName"])
    TEAM_MAP.write_text("[\n" + ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n")


def _candidates(nt_match):
    kickoff = datetime.fromisoformat(nt_match["date"])
    arrangements = {a["ntArrangementId"]: a for a in json.loads(ARRANGEMENTS.read_text())}
    arr = arrangements.get(nt_match["arrangement"]["id"])
    if arr:
        pool = nifs.stage_matches(nifs.current_stage(arr["nifsTournamentId"])["id"])
    else:
        pool = nifs.get(f"matches/?date={kickoff.date().isoformat()}")
    return [m for m in pool if datetime.fromisoformat(m["timestamp"]) == kickoff]


def link(nt_matches):
    """Return {ntEventId: nifs match (list form)} and grow the team map. Raises on any miss."""
    team_map = load_team_map()
    linked, misses = {}, []
    for m in nt_matches:
        home, away = m["teams"]["home"], m["teams"]["away"]
        best = max(
            ((min(_side_score(home, c["homeTeam"], team_map), _side_score(away, c["awayTeam"], team_map)), c)
             for c in _candidates(m)),
            default=(0, None), key=lambda t: t[0])
        if best[0] < THRESHOLD:
            misses.append(m["name"])
            continue
        c = best[1]
        linked[m["gameEngineEventId"]] = c
        for nt_team, nifs_team in ((home, c["homeTeam"]), (away, c["awayTeam"])):
            if nt_team["id"] not in team_map:
                team_map[nt_team["id"]] = {
                    "ntTeamId": nt_team["id"], "ntName": nt_team["webName"],
                    "nifsTeamId": nifs_team["id"], "nifsName": nifs_team["name"],
                    "source": "auto", "verifiedOn": date.today().isoformat()}
    save_team_map(team_map)
    if misses:
        raise LookupError(f"No NIFS match found for: {', '.join(misses)}")
    return linked
