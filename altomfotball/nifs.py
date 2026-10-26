"""NIFS API client. Routes and quirks: docs/nifs-api.md."""

from concurrent.futures import ThreadPoolExecutor

from .fetch import get_json

BASE = "https://v2api.nifs.no/"

PLAYED = 1


def get(path, max_age=1800):
    return get_json(BASE + path, max_age=max_age)


def match(match_id, finished=False):
    return get(f"matches/{match_id}/", max_age=None if finished else 600)


def matches(match_ids):
    """Full match objects for finished matches, fetched in parallel."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(lambda i: match(i, finished=True), match_ids))


def stage_matches(stage_id, team_id=None):
    q = f"?teamId={team_id}" if team_id else ""
    return get(f"stages/{stage_id}/matches/{q}")


def stage_table(stage_id):
    return get(f"stages/{stage_id}/table/")


def team_stages(team_id):
    return get(f"teams/{team_id}/stages/", max_age=6 * 3600)


def current_stages(tournament_id):
    """Every stage of the newest season: one for a league, several for groups or league + knockout phases."""
    stages = get(f"tournaments/{tournament_id}/stages/", max_age=6 * 3600)
    return [s for s in stages if s.get("yearStart") == stages[0].get("yearStart")]
