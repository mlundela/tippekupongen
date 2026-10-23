"""Usage:
  python3 -m altomfotball facts DAY    fetch the coupon and write coupons/<date>-<day>/facts.json
  python3 -m altomfotball render DAY   render site/<date>-<day>.html from facts.json + analysis.json
DAY is SATURDAY, SUNDAY or MIDWEEK.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import analysis, join, nt

ROOT = Path(__file__).resolve().parent.parent


def coupon_dir(coupon):
    return ROOT / "coupons" / f"{coupon['saleStop'][:10]}-{coupon['dayType'].lower()}"


def facts(day):
    coupon = nt.coupons()[day]
    linked = join.link(coupon["matches"])
    with ThreadPoolExecutor(max_workers=3) as pool:
        sheets = list(pool.map(lambda m: analysis.match_facts(m, linked[m["gameEngineEventId"]]), coupon["matches"]))
    out = coupon_dir(coupon)
    out.mkdir(parents=True, exist_ok=True)
    meta = {k: coupon[k] for k in ("dayType", "dayName", "status", "saleStop", "turnover")}
    (out / "facts.json").write_text(json.dumps({"coupon": meta, "matches": sheets}, ensure_ascii=False, indent=1))
    print(out / "facts.json")


def render(day, fragment=None):
    from . import render as r
    coupon = nt.coupons()[day]
    print(r.render(coupon_dir(coupon), ROOT / "site", fragment))


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4) or sys.argv[1] not in ("facts", "render"):
        sys.exit(__doc__)
    {"facts": facts, "render": render}[sys.argv[1]](sys.argv[2].upper(), *sys.argv[3:])
