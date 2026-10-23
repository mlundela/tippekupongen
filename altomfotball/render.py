"""Render a coupon page (Norwegian, phone-first) from coupons/<id>/facts.json + analysis.json.

The page carries our reading of the numbers, not the numbers themselves: analysis.json holds the take,
which stats support the bookmaker's odds and what could turn the match. The tendens is computed here,
from Oddsen's margin-free odds against the public's split.
"""

import json
import re
from datetime import datetime
from html import escape
from pathlib import Path

WEEKDAYS = ["man.", "tir.", "ons.", "tor.", "fre.", "lør.", "søn."]
MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "desember"]
SIGNS = (("home", "H"), ("draw", "U"), ("away", "B"))
KIND = ["", "spik", "halvgardering", "helgardering"]
POSITIONS = {"Keeper": "Keeper", "Defender": "Forsvar", "Midfielder": "Midtbane", "Attacker": "Angrep"}
STATUS = {"suspended": "Utestengt", "injured": "Skadet", "doubtful": "Usikker", "missing": "Ute av troppen",
          "returning": "Tilbake", "card_risk": "Karantenefare"}
VALUE_GAP = 5  # percentage points the odds sit above the public before a sign counts as undervalued
SPIKE_AT = 55  # odds-implied % for a single sign
KEEP_AT = 45   # odds-implied % a sign needs to stay in a two-sign hedge regardless of the public


def tendens(implied, peoples):
    """Spike the favourite at >= SPIKE_AT %. Otherwise two signs: any >= KEEP_AT %, then the signs the
    public underplays most relative to the odds (implied / public), ties to the likelier sign."""
    keys = [k for k, _ in SIGNS]
    top = max(keys, key=lambda k: implied[k])
    if implied[top] >= SPIKE_AT:
        picks = [top]
    else:
        picks = [k for k in keys if implied[k] >= KEEP_AT]
        rest = sorted((k for k in keys if k not in picks),
                      key=lambda k: (implied[k] / max(peoples[k], 1), implied[k]), reverse=True)
        picks = (picks + rest)[:2]
    return "".join(s for k, s in SIGNS if k in picks)


BOMB_BELOW = 20  # a sign the public gives under this % is a «bombe»
MIN_BOMBS = 3


def is_bomb(sign, peoples):
    key = next(k for k, s in SIGNS if s == sign)
    return peoples[key] < BOMB_BELOW


def system(matches):
    """{eventId: signs} for the whole coupon: tendens() per match, then at least MIN_BOMBS bombs at the
    same row count. Each bomb goes on a spike, where the odds sit furthest above the public (implied /
    public), and the half-guard whose weaker sign the odds rate lowest becomes a spike in return."""
    data = {str(m["nt"]["eventId"]): (m["odds"]["implied"], m["nt"]["tips"]["fullTime"]["peoples"])
            for m in matches if m.get("odds")}
    picks = {i: tendens(*d) for i, d in data.items()}
    key = {s: k for k, s in SIGNS}

    def bombs(i):
        return [s for s in picks[i] if is_bomb(s, data[i][1])]

    while sum(len(bombs(i)) for i in picks) < MIN_BOMBS:
        candidates = [(imp[key[s]] / max(peo[key[s]], 1), imp[key[s]], i, s)
                      for i, (imp, peo) in data.items() if len(picks[i]) == 1
                      for _, s in SIGNS if s not in picks[i] and is_bomb(s, peo)]
        doubles = [(min(data[i][0][key[s]] for s in picks[i]), i) for i in picks
                   if len(picks[i]) == 2 and not bombs(i)]
        if not candidates or not doubles:
            break
        _, _, i, s = max(candidates)
        picks[i] = "".join(x for _, x in SIGNS if x in picks[i] + s)
        _, j = min(doubles)
        weaker = min(picks[j], key=lambda x: data[j][0][key[x]])
        picks[j] = picks[j].replace(weaker, "")
    return picks

CSS = """
/* Layout: one column. A printed coupon slip up top; each match is a slip with the take first and the crowd comparison last. */
:root {
  --paper: #f2f5f3; --slip: #ffffff; --ink: #15222b; --muted: #5a6a71; --rule: #d3ddd8;
  --pitch: #0d6a4e; --pen: #2445c4; --pen-soft: #e3e8fb; --warn: #9a5b00;
  --display: "Archivo", "Arial Narrow", system-ui, sans-serif;
  --body: "Source Serif 4", Georgia, "Times New Roman", serif;
  --ui: "Archivo", system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #0f1619; --slip: #172126; --ink: #e6eeea; --muted: #93a4a9; --rule: #2a383d;
  --pitch: #4cc79a; --pen: #8ea2ff; --pen-soft: #222c52; --warn: #e0aa45; color-scheme: dark } }
:root[data-theme="dark"] {
  --paper: #0f1619; --slip: #172126; --ink: #e6eeea; --muted: #93a4a9; --rule: #2a383d;
  --pitch: #4cc79a; --pen: #8ea2ff; --pen-soft: #222c52; --warn: #e0aa45; color-scheme: dark }

* { box-sizing: border-box }
body { margin: 0; background: var(--paper); color: var(--ink); font: 400 16px/1.5 var(--ui);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 20px 48px; -webkit-text-size-adjust: 100% }
.wrap { max-width: 640px; margin: 0 auto; display: grid; gap: 20px }
.num { font-variant-numeric: tabular-nums }

header.top { display: grid; gap: 6px }
.eyebrow { font: 600 12px/1 var(--ui); letter-spacing: .12em; text-transform: uppercase; color: var(--pitch) }
h1 { margin: 0; font: 800 clamp(34px, 9vw, 48px)/.95 var(--display); font-stretch: 75%; letter-spacing: -.01em; text-wrap: balance }
.meta { display: flex; flex-wrap: wrap; gap: 4px 16px; color: var(--muted); font-size: 14px }
.meta b { color: var(--ink); font-weight: 600 }
.intro { display: grid; gap: 10px }
.intro h2 { margin: 0; font: 700 22px/1.2 var(--display); font-stretch: 85%; text-wrap: balance }
.intro p { margin: 0; font: 400 16.5px/1.6 var(--body); max-width: 65ch }

/* Coupon overview: a printed slip with pen marks */
.slip { background: var(--slip); border: 1px solid var(--rule); border-radius: 6px; overflow: hidden }
.slip-head, .slip-row { display: grid; grid-template-columns: 28px minmax(0, 1fr) repeat(3, 34px); align-items: center; gap: 0 4px; padding: 0 10px }
.slip-head { font: 600 11px/1 var(--ui); letter-spacing: .1em; color: var(--muted); padding-block: 10px 6px; border-bottom: 1px solid var(--rule) }
.slip-head span:nth-child(n+3) { text-align: center }
.slip-row { min-height: 44px; border-bottom: 1px dashed var(--rule); text-decoration: none; color: inherit }
.slip-row:last-child { border-bottom: 0 }
.slip-row:focus-visible { outline: 2px solid var(--pen); outline-offset: -2px }
.slip-no { font: 700 15px/1 var(--display); color: var(--muted) }
.slip-name { font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.box { justify-self: center; width: 30px; height: 26px; border: 1.5px solid var(--rule); border-radius: 4px; font-variant-numeric: tabular-nums;
  display: grid; place-items: center; font: 700 12px/1 var(--ui); color: var(--muted) }
.box.on { border-color: var(--pen); background: var(--pen-soft); color: var(--pen); border-width: 2px }
.box.bomb { border-color: var(--warn); color: var(--warn); background: transparent; border-style: dashed }
.mark.bomb { border-color: var(--warn); color: var(--warn); border-style: dashed }
.legend { font-size: 13.5px; color: var(--muted); margin: 0 }
.legend b { color: var(--ink) }

/* Match slip */
article.match { background: var(--slip); border: 1px solid var(--rule); border-radius: 6px; display: grid; gap: 16px; padding: 16px; scroll-margin-top: 12px }
.m-head { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 2px 12px; align-items: start }
.m-no { grid-row: span 2; font: 800 40px/.9 var(--display); font-stretch: 75%; color: var(--pitch); min-width: 1.4ch }
.m-teams { margin: 0; font: 750 24px/1.1 var(--display); font-stretch: 85%; text-wrap: balance }
.m-teams .vs { color: var(--muted); font-weight: 400 }
.m-sub { color: var(--muted); font-size: 13px }
.headline { margin: 0; font: 600 19px/1.35 var(--body); text-wrap: balance }
.take { display: grid; gap: 10px }
.take p { margin: 0; font: 400 16.5px/1.6 var(--body); max-width: 65ch }

.reads { display: grid; gap: 14px }
.read h3, .crowd h3 { margin: 0 0 8px; font: 700 11px/1 var(--ui); letter-spacing: .12em; text-transform: uppercase }
.read.signal h3 { color: var(--pitch) } .read.noise h3 { color: var(--warn) } .crowd h3 { color: var(--pen) }
.read ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px }
.read li { display: grid; gap: 2px; padding-left: 12px; border-left: 2px solid var(--rule) }
.read.signal li { border-left-color: var(--pitch) } .read.noise li { border-left-color: var(--warn) }
.read .stat { font: 700 14.5px/1.3 var(--ui); font-variant-numeric: tabular-nums }
.read .why { font-size: 14.5px; line-height: 1.45; color: var(--muted) }

/* Crowd vs us */
.crowd { display: grid; gap: 8px; border-top: 1px solid var(--rule); padding-top: 14px }
.crowd p { margin: 0; font-size: 14.5px; line-height: 1.5 }
.dist { display: grid; grid-template-columns: 76px repeat(3, minmax(0, 1fr)); gap: 4px 6px; align-items: center; font-variant-numeric: tabular-nums }
.dist .lbl { font-size: 12px; color: var(--muted) }
.dist .hd { font: 700 11px/1 var(--ui); color: var(--muted); text-align: center; letter-spacing: .08em }
.cell { position: relative; height: 26px; border-radius: 3px; background: var(--paper); overflow: hidden; display: grid; place-items: center; font: 600 12.5px/1 var(--ui) }
.cell i { position: absolute; inset: auto 0 0 0; background: var(--rule) }
.cell span { position: relative }
.us .cell i { background: var(--pen-soft) }
.us .cell.value { outline: 2px solid var(--pen); outline-offset: -2px; color: var(--pen) }
.us .lbl { color: var(--pen); font-weight: 700 }
.verdict { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; font-size: 13px; color: var(--muted) }
.marks { display: flex; gap: 4px }
.mark { width: 26px; height: 26px; border-radius: 50%; border: 2px solid var(--pen); color: var(--pen); display: grid; place-items: center; font: 700 13px/1 var(--ui) }
.odds { font-size: 12.5px; color: var(--muted); font-variant-numeric: tabular-nums }

/* Key players: one card per player named in the analysis */
.players h3 { margin: 0 0 8px; font: 700 11px/1 var(--ui); letter-spacing: .12em; text-transform: uppercase; color: var(--muted) }
.p-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 250px), 1fr)); gap: 10px }
.player { border: 1px solid var(--rule); border-radius: 6px; padding: 12px; display: grid; gap: 10px; background: var(--paper); min-width: 0 }
.p-head { display: grid; gap: 2px }
.p-name { font: 700 16px/1.2 var(--display); font-stretch: 90% }
.p-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px }
.p-stars { font-size: 15px; letter-spacing: 1px; color: var(--pen); white-space: nowrap }
.p-stars .off { color: var(--rule) }
.p-rating { font-size: 12px; color: var(--muted) }
.p-meta { font-size: 12.5px; color: var(--muted) }
.p-status { justify-self: start; margin-top: 4px; font: 600 11px/1 var(--ui); letter-spacing: .04em; padding: 4px 6px; border-radius: 3px; border: 1px solid currentColor }
.p-status.s-suspended, .p-status.s-injured, .p-status.s-missing { color: var(--warn) }
.p-status.s-doubtful { color: var(--ink) }
.p-status.s-returning { color: var(--pitch) }
.p-status.s-card_risk { color: var(--muted) }
.p-why { font-size: 12.5px; color: var(--muted); margin: 0 }
.p-stats { margin: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 6px }
.p-stats div { display: grid; gap: 1px; min-width: 0 }
.p-stats dt { font-size: 11px; color: var(--muted); line-height: 1.2 }
.p-stats dd { margin: 0; font: 700 17px/1.2 var(--ui); font-variant-numeric: tabular-nums }
.p-stats dd small { font: 400 11.5px/1 var(--ui); color: var(--muted) }

.empty { color: var(--muted); font-size: 14px; margin: 0 }
footer { font-size: 12.5px; color: var(--muted); display: grid; gap: 8px; max-width: 65ch }
footer dl { margin: 0; display: grid; gap: 4px }
footer dt { font-weight: 700; color: var(--ink); display: inline }
footer dd { margin: 0; display: inline }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth } }
"""


def _dt(ts):
    return datetime.fromisoformat(ts)


def _kick(ts):
    d = _dt(ts)
    return f"{WEEKDAYS[d.weekday()]} {d.hour:02d}.{d.minute:02d}"


def _date_long(ts):
    d = _dt(ts)
    return f"{d.day}. {MONTHS[d.month - 1]}"


def _nok(amount):
    v = float(amount)
    return f"{v / 1e6:.2f}".replace(".", ",") + " mill. kr" if v >= 1e6 else f"{round(v):,}".replace(",", " ") + " kr"


def _dist_row(label, dist, css="", crowd=None):
    cells = []
    for key, _ in SIGNS:
        v = dist[key]
        value = crowd is not None and v - crowd[key] >= VALUE_GAP
        cells.append(f'<div class="cell{" value" if value else ""}"><i style="height:{v}%"></i><span>{v}</span></div>')
    return f'<div class="row-wrap {css}" style="display:contents"><span class="lbl">{label}</span>{"".join(cells)}</div>'


def _reads(css, title, items):
    if not items:
        return ""
    lis = "".join(f'<li><span class="stat">{escape(i["stat"])}</span><span class="why">{escape(i["text"])}</span></li>' for i in items)
    return f'<section class="read {css}"><h3>{title}</h3><ul>{lis}</ul></section>'


def _dec(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",")


KEY_START_SHARE = 0.5          # started at least half the team's league matches
KEY_CONTRIBUTION_SHARE = 0.15  # or involved (goals + assists) in at least this share of the team's league goals
KEY_MIN_CONTRIBUTIONS = 3
STAR_CUTS = ((0.15, 3), (0.50, 2))  # FotMob season-rating rank in the league: top 15 % ★★★, top 50 % ★★, else ★


def stars(season_rating):
    if not season_rating:
        return None
    share = season_rating["rank"] / season_rating["of"]
    return next((n for cut, n in STAR_CUTS if share <= cut), 1)


def is_key_player(p, team):
    """A regular starter, or a player whose goals and assists carry a real share of the team's scoring.
    Squad players named in the text (long-term injured, bit-part) get no card."""
    played = (team.get("overall") or {}).get("p") or 0
    goals = (team.get("overall") or {}).get("gf") or 0
    contributions = p["goals"] + p["assists"]
    return bool(played and p["starts"] >= KEY_START_SHARE * played) or (
        contributions >= KEY_MIN_CONTRIBUTIONS and goals and contributions >= KEY_CONTRIBUTION_SHARE * goals)


def _mentioned(f, a):
    """Players from either team named in the match text, in order of first mention.
    A bare surname counts only when no other player on the two teams shares it."""
    parts = [a["headline"], *a["take"], a.get("crowd", "")]
    parts += [f'{i["stat"]} {i["text"]}' for i in (a.get("signal") or []) + (a.get("noise") or [])]
    text = " ".join(parts)
    pool = [(side, p) for side in ("home", "away") for p in f[side].get("players") or []]
    surnames = {}
    for _, p in pool:
        surnames[p["name"].split()[-1]] = surnames.get(p["name"].split()[-1], 0) + 1
    found = {}
    for side, p in pool:
        last = p["name"].split()[-1]
        needles = [p["name"]] + ([last] if len(last) >= 4 and surnames[last] == 1 else [])
        hits = [m.start() for n in needles for m in re.finditer(rf"(?<!\w){re.escape(n)}(?!\w)", text)]
        if hits and p["id"] not in found:
            found[p["id"]] = (min(hits), side, p)
    return [(side, p) for _, side, p in sorted(found.values(), key=lambda t: t[0])]


def _player_card(team, p):
    meta = [team["name"]] + ([POSITIONS.get(p["position"])] if POSITIONS.get(p["position"]) else [])
    meta += [f'nr. {p["shirtNumber"]}'] if p.get("shirtNumber") else []
    stats = []
    if p["goals"] or p["assists"]:
        pens = f' <small>({p["penalties"]} str.)</small>' if p["penalties"] else ""
        stats += [("Mål", f'{p["goals"]}{pens}'), ("Målgivende", p["assists"]),
                  ("Siste 5", f'{p["last5Goals"]}+{p["last5Assists"]} <small>mål+mg</small>')]
    stats += [("Kamper", f'{p["apps"]} <small>({p["starts"]} fra start)</small>'), ("Minutter", p["minutes"])]
    if p["goals"] and p.get("goalShare") is not None:
        stats.append(("Andel av lagets mål", f'{round(100 * p["goalShare"])} %'))
    if p["yellows"] or p["reds"]:
        stats.append(("Kort", f'{p["yellows"]} gule' + (f', {p["reds"]} rødt' if p["reds"] else "")))
    if p.get("avgRatingLast5"):
        stats.append(("Karakter siste 5", _dec(p["avgRatingLast5"])))
    tiles = "".join(f"<div><dt>{escape(k)}</dt><dd>{v}</dd></div>" for k, v in stats)
    st = p.get("status")
    badge = f'<span class="p-status s-{st["kind"]}">{STATUS[st["kind"]]}</span>' if st else ""
    why = f'<p class="p-why">{escape(st["reason"][:1].upper() + st["reason"][1:])}.</p>' if st else ""
    league = escape(team["league"]["name"]) if team.get("league") else "serien"
    sr, n = p.get("seasonRating"), stars(p.get("seasonRating"))
    star_html = (f'<span class="p-stars" role="img" aria-label="{n} av 3 stjerner">{"★" * n}<span class="off">{"★" * (3 - n)}</span></span>'
                 if n else "")
    rating = (f'<span class="p-rating">FotMob-snitt {_dec(sr["rating"], 2)} · nr. {sr["rank"]} av {sr["of"]} i {escape(sr["league"])}</span>'
              if sr else '<span class="p-rating">For få minutter til FotMob-rating i ligaen</span>')
    return (f'<div class="player"><div class="p-head"><div class="p-top"><span class="p-name">{escape(p["name"])}</span>{star_html}</div>'
            f'<span class="p-meta">{escape(" · ".join(meta))}</span>{rating}{badge}</div>'
            f'<dl class="p-stats" aria-label="Tall fra {league}">{tiles}</dl>{why}</div>')


def _players(f, a):
    named = [(side, p) for side, p in _mentioned(f, a) if is_key_player(p, f[side])]
    if not named:
        return ""
    league = f["home"].get("league", {}).get("name", "serien")
    cards = "".join(_player_card(f[side], p) for side, p in named)
    return f'<section class="players"><h3>Nøkkelspillere · {escape(league)}</h3><div class="p-grid">{cards}</div></section>'


def _match(f, a, idx, t):
    h, aw = f["home"]["name"], f["away"]["name"]
    tips = f["nt"]["tips"]["fullTime"]
    round_txt = f', {f["round"]}. runde' if f.get("round") else ""
    head = f"""
  <div class="m-head">
    <span class="m-no num">{idx}</span>
    <h2 class="m-teams">{escape(h)} <span class="vs">–</span> {escape(aw)}</h2>
    <div class="m-sub">{_kick(f["kickoff"])} · {escape(f["competition"])}{round_txt}{(" · " + escape(f["stadium"])) if f.get("stadium") else ""}</div>
  </div>"""
    if not a:
        return f'<article class="match" id="kamp-{idx}">{head}<p class="empty">Vurderingen er ikke skrevet ennå.</p></article>'

    take = "".join(f"<p>{escape(p)}</p>" for p in a["take"])
    odds = f.get("odds")
    dist = odds_line = verdict = ""
    if odds:
        dist = (f'<div class="dist" role="table" aria-label="Fordeling H, U, B i prosent">'
                f'<span></span><span class="hd">H</span><span class="hd">U</span><span class="hd">B</span>'
                f'{_dist_row("Folket", tips["peoples"])}'
                f'{_dist_row("Oddsen", odds["implied"], "us", tips["peoples"])}</div>')
        o = odds["odds"]
        odds_line = (f'<span class="odds">Odds {o["home"]:.2f} · {o["draw"]:.2f} · {o["away"]:.2f}'.replace(".", ",")
                     + f' (margin {str(odds["margin"]).replace(".", ",")} %)</span>')
        marks = "".join(f'<span class="mark{" bomb" if is_bomb(c, tips["peoples"]) else ""}">{c}</span>' for c in t)
        n_bombs = sum(is_bomb(c, tips["peoples"]) for c in t)
        bomb_txt = f'<span>med bombe (folket under {BOMB_BELOW} %)</span>' if n_bombs else ""
        verdict = f'<div class="verdict"><span>Tendens</span><span class="marks">{marks}</span><span>{KIND[len(t)]}</span>{bomb_txt}</div>'
    return f"""
<article class="match" id="kamp-{idx}">{head}
  <p class="headline">{escape(a["headline"])}</p>
  <div class="take">{take}</div>
  <div class="reads">
    {_reads("signal", "Tallene som støtter oddsen", a.get("signal"))}
    {_reads("noise", "Dette kan snu kampen", a.get("noise"))}
  </div>
  {_players(f, a)}
  <section class="crowd">
    <h3>Folket mot oddsen</h3>
    {dist}
    {odds_line}
    <p>{escape(a["crowd"])}</p>
    {verdict}
  </section>
</article>"""


def render(coupon_dir, site_dir, fragment_path=None):
    facts = json.loads((coupon_dir / "facts.json").read_text())
    analysis_file = coupon_dir / "analysis.json"
    analysis = json.loads(analysis_file.read_text()) if analysis_file.exists() else {}
    c = facts["coupon"]
    matches = sorted(facts["matches"], key=lambda m: m["nt"]["line"])
    first = min(m["kickoff"] for m in matches)
    per_match = {str(m["nt"]["eventId"]): analysis.get(str(m["nt"]["eventId"])) for m in matches}

    picks = {str(m["nt"]["eventId"]): "" for m in matches} | system(matches)
    rows = []
    for m in matches:
        t = picks[str(m["nt"]["eventId"])]
        peoples = m["nt"]["tips"]["fullTime"]["peoples"]
        boxes = "".join(
            f'<span class="box{" on" if s in t else ""}{" bomb" if s in t and is_bomb(s, peoples) else ""}"'
            f' aria-label="{s}: folket {peoples[k]} %{", valgt" if s in t else ""}">{peoples[k]}</span>' for k, s in SIGNS)
        rows.append(f'<a class="slip-row" href="#kamp-{m["nt"]["line"]}"><span class="slip-no num">{m["nt"]["line"]}</span>'
                    f'<span class="slip-name">{escape(m["home"]["name"])} – {escape(m["away"]["name"])}</span>{boxes}</a>')

    chosen = picks
    picks = list(picks.values())
    n_bombs = sum(is_bomb(s, m["nt"]["tips"]["fullTime"]["peoples"]) for m in matches for s in chosen[str(m["nt"]["eventId"])])
    legend = '<p class="legend">Trykk på en kamp for vurderingen.</p>'
    if all(picks):
        n_rows = 1
        for p in picks:
            n_rows *= len(p)
        counts = {k: sum(len(p) == k for p in picks) for k in (1, 2, 3)}
        names = {1: ("spik", "spiker"), 2: ("halvgardering", "halvgarderinger"), 3: ("helgardering", "helgarderinger")}
        parts = [f"{n} {names[k][n != 1]}" for k, n in counts.items() if n]
        legend = (f'<p class="legend">Tallene er folkets prosent. Markerte ruter er tendensen fra oddsen: {", ".join(parts)}, '
                  f'med <b class="num">{n_bombs}</b> bomber (stiplet, tegn folket gir under {BOMB_BELOW} %). Som system blir det '
                  f'<b class="num">{n_rows}</b> rekker ({_nok(n_rows)} med 1 kr per rekke). Trykk på en kamp for vurderingen.</p>')

    cp = analysis.get("_coupon") or {}
    intro = ""
    if cp:
        intro = (f'<section class="intro"><h2>{escape(cp["headline"])}</h2>'
                 + "".join(f"<p>{escape(p)}</p>" for p in cp["intro"]) + "</section>")

    title = f'{c["dayName"]}skupongen' if c["dayType"] != "MIDWEEK" else "Midtukekupongen"
    body = f"""<title>{title} {_date_long(first)}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">
<style>{CSS}</style>
<div class="wrap">
  <header class="top">
    <span class="eyebrow">Tipping · {c["dayName"]} {_date_long(first)}</span>
    <h1>{title}</h1>
    <div class="meta"><span>Spillestopp <b>{_kick(c["saleStop"])}</b></span><span>Omsetning <b>{_nok(c["turnover"]["amount"])}</b></span><span><b>12</b> kamper</span></div>
  </header>
  {intro}
  <nav class="slip" aria-label="Kupongen">
    <div class="slip-head"><span>NR</span><span>KAMP</span><span>H</span><span>U</span><span>B</span></div>
    {"".join(rows)}
  </nav>
  {legend}
  {"".join(_match(m, per_match[str(m["nt"]["eventId"])], m["nt"]["line"], chosen[str(m["nt"]["eventId"])]) for m in matches)}
  <footer>
    <dl>
      <div><dt>xG</dt> <dd>forventede mål: hvor mange mål sjansene et lag skaper, er verdt i snitt.</dd></div>
      <div><dt>PDO</dt> <dd>andel skudd på mål som blir mål, pluss andel motstanderskudd på mål som reddes. 1,00 er normalt. Langt over eller under pleier å jevne seg ut.</dd></div>
      <div><dt>Oddsen</dt> <dd>oddsen fra Norsk Tippings Oddsen, regnet om til sannsynlighet uten bookmakerens margin. Innrammede tall er tegn der oddsen ligger minst {VALUE_GAP} prosentpoeng over folkets fordeling.</dd></div>
      <div><dt>Tendens</dt> <dd>spik når oddsen gir favoritten minst {SPIKE_AT} %. Ellers halvgardering med tegn over {KEEP_AT} % og tegnene folket undervurderer mest i forhold til oddsen.</dd></div>
      <div><dt>Stjerner</dt> <dd>nøkkelspillerens plass blant alle spillere i ligaen på FotMobs snittkarakter for sesongen: ★★★ topp 15 %, ★★ topp halvdel, ★ resten.</dd></div>
      <div><dt>Bombe</dt> <dd>et tegn folket gir under {BOMB_BELOW} %. Systemet har minst {MIN_BOMBS}. Mangler det bomber, legges de på spikene der oddsen ligger mest over folket, og halvgarderingen med det svakeste tegnet blir spik, slik at antallet rekker er det samme.</dd></div>
    </dl>
    <span>Statistikk fra NIFS, folkets fordeling og odds fra Norsk Tipping. Hentet {datetime.now().strftime("%d.%m.%Y %H.%M")}. Skader og utestengelser fra FotMob. Karantenefare er beregnet fra gule kort i NIFS etter seriens regler.</span>
    <span>18-årsgrense for pengespill. Spill ansvarlig.</span>
  </footer>
</div>"""
    site_dir.mkdir(parents=True, exist_ok=True)
    out = site_dir / f"{coupon_dir.name}.html"
    out.write_text(f'<!doctype html>\n<html lang="nb">\n<head>\n<meta charset="utf-8">\n'
                   f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n{body}\n</body>\n</html>\n')
    if fragment_path:
        Path(fragment_path).write_text(body)
    return out
