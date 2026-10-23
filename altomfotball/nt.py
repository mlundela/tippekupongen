"""Norsk Tipping pool-game coupons. Shape: docs/norsk-tipping-api.md."""

from .fetch import get_json

LIVE_INFO = "https://api.norsk-tipping.no/PoolGamesSportInfo/v1/api/tipping/live-info"

DAY_NAMES = {"SATURDAY": "Lørdag", "SUNDAY": "Søndag", "MIDWEEK": "Midtuke"}


def coupons(max_age=600):
    """Open coupons keyed by dayType. Tips are zipped onto their matches by position."""
    out = {}
    for day in get_json(LIVE_INFO, max_age=max_age)["gameDays"]:
        game = day["game"]
        matches = sorted(game["matches"], key=lambda m: m["gameEngineSortingNumber"])
        for i, m in enumerate(game["matches"]):
            m["tips"] = {
                period: {who: game["tips"][period][who][i] for who in ("expert", "peoples")}
                for period in ("fullTime", "halfTime")
            }
        out[day["dayType"]] = {
            "dayType": day["dayType"],
            "dayName": DAY_NAMES.get(day["dayType"], day["dayType"]),
            "status": game["status"],
            "saleStop": game["sales"]["fullTime"]["saleStopDate"],
            "turnover": game["sales"]["fullTime"]["saleAmount"],
            "matches": matches,
        }
    return out
