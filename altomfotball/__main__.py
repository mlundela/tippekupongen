"""Usage:
  python3 -m altomfotball next         print the DAY of the open coupon with the earliest sale stop
  python3 -m altomfotball facts DAY    fetch the coupon and write coupons/<date>-<day>/facts.json
  python3 -m altomfotball check DAY    validate analysis.json against facts.json
  python3 -m altomfotball render DAY   render site/<date>-<day>.html from facts.json + analysis.json
DAY is SATURDAY, SUNDAY or MIDWEEK.
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import analysis, join, nt, oddsen

ROOT = Path(__file__).resolve().parent.parent


def coupon_dir(coupon):
    return ROOT / "coupons" / f"{coupon['saleStop'][:10]}-{coupon['dayType'].lower()}"


def facts(day):
    coupon = nt.coupons()[day]
    linked = join.link(coupon["matches"])
    with ThreadPoolExecutor(max_workers=3) as pool:
        sheets = list(pool.map(lambda m: analysis.match_facts(m, linked[m["gameEngineEventId"]]), coupon["matches"]))
    odds = oddsen.odds_for(coupon["matches"])
    for sheet in sheets:
        sheet["odds"] = odds.get(sheet["nt"]["eventId"])
    missing = [s["nt"]["name"] for s in sheets if not s["odds"]]
    if missing:
        print("No Oddsen odds for:", ", ".join(missing), file=sys.stderr)
    out = coupon_dir(coupon)
    out.mkdir(parents=True, exist_ok=True)
    meta = {k: coupon[k] for k in ("dayType", "dayName", "status", "saleStop", "turnover")}
    (out / "facts.json").write_text(json.dumps({"coupon": meta, "matches": sheets}, ensure_ascii=False, indent=1))
    print(out / "facts.json")


def next_day():
    now = datetime.now(timezone.utc)
    upcoming = [c for c in nt.coupons().values() if datetime.fromisoformat(c["saleStop"]) > now]
    if not upcoming:
        sys.exit("No open coupon")
    print(min(upcoming, key=lambda c: datetime.fromisoformat(c["saleStop"]))["dayType"])


def _texts(field, value, n=None):
    """Errors for a field that must be a non-empty string, or a list of n (or any number of) them."""
    if n is None:
        return [] if isinstance(value, str) and value.strip() else [f"{field}: missing text"]
    if not isinstance(value, list) or not value or not all(isinstance(p, str) and p.strip() for p in value):
        return [f"{field}: must be a list of non-empty strings"]
    return [] if n == "any" or len(value) == n else [f"{field}: {len(value)} paragraphs, want {n}"]


def check(day):
    """Exit non-zero unless analysis.json covers every match in facts.json in the shape render() expects."""
    out = coupon_dir(nt.coupons()[day])
    facts = json.loads((out / "facts.json").read_text())
    try:
        a = json.loads((out / "analysis.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError) as e:
        sys.exit(f"analysis.json: {e}")
    ids = {str(m["nt"]["eventId"]): m["nt"]["name"] for m in facts["matches"]}
    cp = a.get("_coupon") or {}
    errors = _texts("_coupon.headline", cp.get("headline")) + _texts("_coupon.intro", cp.get("intro"), "any")
    errors += [f"{k}: not a match on this coupon" for k in a if k != "_coupon" and k not in ids]
    for k, name in ids.items():
        m = a.get(k)
        if not isinstance(m, dict):
            errors.append(f"{k} ({name}): missing")
            continue
        errors += _texts(f"{k}.headline", m.get("headline")) + _texts(f"{k}.take", m.get("take"), 2)
        errors += _texts(f"{k}.crowd", m.get("crowd"))
        for field in ("signal", "noise"):
            items = m.get(field)
            if not isinstance(items, list) or not items:
                errors.append(f"{k}.{field}: must be a non-empty list")
                continue
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"{k}.{field}[{i}]: must be {{stat, text}}")
                    continue
                errors += _texts(f"{k}.{field}[{i}].stat", item.get("stat")) + _texts(f"{k}.{field}[{i}].text", item.get("text"))
    # The page's words for the system are «vår anbefaling», «sikker», «halvgardering», «bombe» (AGENTS.md).
    errors += [f"forbidden word «{w}»" for w in sorted(set(re.findall(r"(?i)\b(tendens\w*|spik\w*)", json.dumps(a, ensure_ascii=False))))]
    if errors:
        sys.exit("\n".join(errors))
    print(f"{out / 'analysis.json'}: ok")


def render(day, fragment=None):
    from . import render as r
    coupon = nt.coupons()[day]
    print(r.render(coupon_dir(coupon), ROOT / "site", fragment))


if __name__ == "__main__":
    if sys.argv[1:] == ["next"]:
        next_day()
    elif len(sys.argv) in (3, 4) and sys.argv[1] in ("facts", "check", "render"):
        {"facts": facts, "check": check, "render": render}[sys.argv[1]](sys.argv[2].upper(), *sys.argv[3:])
    else:
        sys.exit(__doc__)
