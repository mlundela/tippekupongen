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
from zoneinfo import ZoneInfo

WEEKDAYS = ["man.", "tir.", "ons.", "tor.", "fre.", "lør.", "søn."]
MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "desember"]
SIGNS = (("home", "H"), ("draw", "U"), ("away", "B"))
KIND = ["", "sikker", "halvgardering", "helgardering"]
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

# Dagkamp: the same page in daylight, on white. Volt and orange are too pale on white,
# so good and bad darken to grass and brick (both ≥ 5:1 on the cards too); the player cards are chalk.
LIGHT = """--bg: #fff; --ink: #15160f; --good: #377000; --bad: #b8321a; --slip: #fff; --card: #f4f2ea;
  color-scheme: light;"""

CSS = """
/* Flomlys: a night match under floodlights. One column, square edges.
   Type as on svelte.dev: DM Serif Display for headings, EB Garamond (Georgia on low-res screens) for the prose,
   Fira Sans for labels, Fira Mono for numbers; everything sized from the --font-* tokens below.
   Four colours: background, ink, good (volt, also the accent) and bad. Every other shade is a mix of those.
   Good marks positive labels (in form, back from injury), bad the negative ones (injured, suspended, what could turn the match).
   Dark by default; Dagkamp (light) when the browser prefers it. data-theme on <html> overrides either way. */
:root {
  --bg: #0e0f0c; --ink: #f1efe6; --good: #c6ff3d; --bad: #ff5c39; --accent: var(--good);
  --slip: color-mix(in srgb, var(--ink) 4%, var(--bg)); --tint: color-mix(in srgb, var(--ink) 12%, var(--bg));
  --muted: color-mix(in srgb, var(--ink) 64%, var(--bg)); --rule: color-mix(in srgb, var(--ink) 20%, var(--bg));
  --card: var(--slip);
  --display: "DM Serif Display", Georgia, serif;
  --body: Georgia, serif;
  --ui: "Fira Sans", -apple-system, system-ui, sans-serif;
  --num: "Fira Mono", ui-monospace, monospace;
  /* Sizes, weights and line heights from svelte.dev's --sk-font-* (1rem = 10px there) */
  --fs-h1: 36px; --fs-h2: 30px; --fs-h3: 24px; --fs-body: 18px; --fs-body-small: 16px;
  --font-h1: 500 var(--fs-h1)/1.2 var(--display); --font-h2: 500 var(--fs-h2)/1.2 var(--display);
  --font-h3: 500 var(--fs-h3)/1.2 var(--display);
  --font-body: 400 var(--fs-body)/1.5 var(--body); --font-body-small: 400 var(--fs-body-small)/1.5 var(--body);
  --font-ui-medium: 400 16px/1.5 var(--ui); --font-ui-small: 400 13px/1.5 var(--ui);
  --font-mono: 400 14px/1.7 var(--num);
  color-scheme: dark;
}
/* Like svelte.dev: Garamond only on sharp screens, where it renders well, and larger to match Georgia's x-height */
@media (-webkit-min-device-pixel-ratio: 1.75), (min-resolution: 1.75dppx) {
  :root { --body: "EB Garamond", Georgia, serif; --fs-body: 22px; --fs-body-small: 20px } }
@media (min-width: 800px) { :root { --fs-h1: 54px } }
@media (prefers-color-scheme: light) { :root:not([data-theme="dark"]) { """ + LIGHT + """ } }
:root[data-theme="light"] { """ + LIGHT + """ }

* { box-sizing: border-box }
body { margin: 0; background: var(--bg); color: var(--ink); font: var(--font-ui-medium);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 20px 48px; -webkit-text-size-adjust: 100% }
.wrap { max-width: 640px; margin: 0 auto; display: grid; gap: 20px }
.num { font-variant-numeric: tabular-nums }

header.top { display: grid; gap: 6px }
.eyebrow { font: var(--font-ui-small); letter-spacing: .06em; text-transform: uppercase; color: var(--accent) }
h1 { margin: 0; font: var(--font-h1); text-wrap: balance }
.meta { display: flex; flex-wrap: wrap; gap: 4px 16px; color: var(--muted); font: var(--font-ui-small) }
.meta b { color: var(--ink); font-weight: 600 }
.intro { display: grid; gap: 10px }
.intro h2 { margin: 0; font: var(--font-h2); text-wrap: balance }
.intro p { margin: 0; font: var(--font-body); max-width: 65ch }

/* Coupon overview: a slip with marked boxes */
.slip { background: var(--slip); border: 1px solid var(--rule); overflow: hidden }
.slip-head, .slip-row { display: grid; grid-template-columns: 28px minmax(0, 1fr) repeat(3, 34px); align-items: center; gap: 0 4px; padding: 0 10px }
.slip-head { font: var(--font-ui-small); letter-spacing: .1em; color: var(--muted); padding-block: 10px 6px; border-bottom: 1px solid var(--rule) }
.slip-head span:nth-child(n+3) { text-align: center }
.slip-row { min-height: 44px; border-bottom: 1px dashed var(--rule); text-decoration: none; color: inherit }
.slip-row:last-child { border-bottom: 0 }
.slip-row:focus-visible { outline: 2px solid var(--ink); outline-offset: -2px }
.slip-no { font: var(--font-mono); color: var(--muted) }
.slip-name { font: var(--font-ui-medium); overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.box { justify-self: center; width: 30px; height: 26px; border: 1.5px solid var(--rule); font-variant-numeric: tabular-nums;
  display: grid; place-items: center; font: var(--font-mono); color: var(--muted) }
.box.on { border: 2px solid var(--accent); background: var(--accent); color: var(--bg) }
/* Bombs are a pick, not a warning: accent, dashed */
.box.bomb { border-color: var(--accent); color: var(--accent); background: transparent; border-style: dashed }
.mark.bomb { border-style: dashed }
.legend { font: var(--font-ui-small); color: var(--muted); margin: 0 }
.legend b { color: var(--ink) }

/* Match: no box, a rule on top, so the text runs to the page gutter */
article.match { display: grid; gap: 16px; padding: 18px 0 8px; border-top: 2px solid var(--ink); scroll-margin-top: 12px }
.m-head { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 2px 12px; align-items: start }
.m-no { grid-row: span 2; font: var(--font-h2); color: var(--accent); min-width: 1.4ch }
.m-teams { margin: 0; font: var(--font-h2); text-wrap: balance }
.m-teams .vs { color: var(--muted); font-weight: 400 }
.m-sub { color: var(--muted); font: var(--font-ui-small) }
.headline { margin: 0; font: var(--font-h3); text-wrap: balance }
.take { display: grid; gap: 10px }
.take p { margin: 0; font: var(--font-body); max-width: 65ch }

/* «Støtter folket» in ink; «kan snu kampen» in the bad colour, dashed */
.reads { display: grid; gap: 14px }
.read h3, .crowd h3 { margin: 0 0 8px; font: var(--font-ui-small); letter-spacing: .12em; text-transform: uppercase }
.read.signal h3, .crowd h3 { color: var(--ink) } .read.noise h3 { color: var(--bad) }
.read ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px }
.read li { display: grid; gap: 2px; padding-left: 12px; border-left: 2px solid var(--ink) }
.read.noise li { border-left: 2px dashed var(--bad) }
.read .stat { font: var(--font-mono); font-variant-numeric: tabular-nums }
.read .why { font: var(--font-ui-medium); color: var(--muted) }

/* Crowd vs odds */
.crowd { display: grid; gap: 8px; border-top: 1px solid var(--rule); padding-top: 14px }
.crowd p { margin: 0; font: var(--font-body-small) }
.dist { display: grid; grid-template-columns: 76px repeat(3, minmax(0, 1fr)); gap: 4px 6px; align-items: center; font-variant-numeric: tabular-nums }
.dist .lbl { font: var(--font-ui-small); color: var(--muted) }
.dist .hd { font: var(--font-ui-small); color: var(--muted); text-align: center; letter-spacing: .08em }
.cell { position: relative; height: 26px; background: var(--bg); overflow: hidden; display: grid; place-items: center; font: var(--font-mono) }
.cell i { position: absolute; inset: auto 0 0 0; background: var(--rule) }
.cell span { position: relative }
.us .cell i { background: var(--tint) }
.us .cell.value { outline: 2px solid var(--ink); outline-offset: -2px }
.us .lbl { color: var(--ink); font-weight: 700 }
.verdict { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; font: var(--font-ui-small); color: var(--muted) }
.marks { display: flex; gap: 4px }
.mark { width: 26px; height: 26px; border-radius: 50%; border: 2px solid var(--accent); color: var(--accent); display: grid; place-items: center; font: var(--font-mono) }
.odds { font: var(--font-mono); color: var(--muted); font-variant-numeric: tabular-nums }

/* Key players: one card per player named in the analysis */
.players h3 { margin: 0 0 8px; font: var(--font-ui-small); letter-spacing: .12em; text-transform: uppercase; color: var(--muted) }
.p-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 250px), 1fr)); gap: 10px }
.player { border: 1px solid var(--rule); padding: 14px; display: grid; gap: 14px; align-content: start; background: var(--card); min-width: 0 }
.p-head { display: grid; gap: 3px }
.p-name { font: var(--font-h3) }
.p-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px }
.p-stars { font-size: 15px; letter-spacing: 1px; color: var(--accent); white-space: nowrap }
.p-stars .off { color: var(--rule) }
.p-meta { font: var(--font-ui-small); color: var(--muted) }
.p-status { justify-self: start; margin-top: 6px; font: var(--font-ui-small); letter-spacing: .04em; padding: 4px 6px; border: 1px solid currentColor }
.p-status.s-suspended, .p-status.s-injured, .p-status.s-missing { color: var(--bad) }
.p-status.s-doubtful { color: var(--ink) }
.p-status.s-returning { color: var(--good) }
.p-status.s-card_risk { color: var(--muted) }
.p-why { font: var(--font-ui-small); color: var(--muted); margin: 2px 0 0 }
/* Tier 1: what makes the player key, as {goals}({penalties})+{assists} */
.p-hero { display: grid; gap: 4px }
.p-hero b { font: 500 36px/1.2 var(--num); font-variant-numeric: tabular-nums; letter-spacing: -.06em; color: var(--accent) }
.p-hero b small { font-size: .4em; font-weight: 400; letter-spacing: 0; color: var(--muted); margin-left: 2px }
.p-hero b em { font-style: normal; font-size: .62em; font-weight: 500; letter-spacing: -.02em; margin-left: 4px; color: var(--ink) }
.p-hero > span { font: var(--font-ui-small); color: var(--muted) }
/* Tier 2: form. Hot form takes the good colour; no goals or assists in five fades. */
.p-form { margin: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; font: var(--font-ui-small); color: var(--muted) }
.p-form b { font: var(--font-mono); color: var(--ink) }
.p-form.hot b { color: var(--good); font-weight: 700 }
.p-form.cold b { color: var(--muted) }
.p-form em { font: var(--font-ui-small); font-style: normal; letter-spacing: .08em; text-transform: uppercase; color: var(--good);
  border: 1px solid currentColor; padding: 3px 5px }
/* How much the team leans on the player: goal share as a bar, FotMob rating as a dot among teammates */
.p-team { display: grid; gap: 14px; padding-top: 12px; border-top: 1px solid var(--rule) }
.p-team h4 { margin: 0; font: var(--font-ui-small); letter-spacing: .12em; text-transform: uppercase; color: var(--muted) }
.p-role { display: grid; gap: 7px }
.p-big { margin: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px }
.p-big b { font: 500 24px/1.2 var(--num); font-variant-numeric: tabular-nums; letter-spacing: -.02em }
.p-big span { font: var(--font-ui-small); color: var(--muted) }
.p-big b small { font: var(--font-ui-small); letter-spacing: 0; color: var(--muted); margin-right: 3px }
.p-bar { display: flex; height: 8px; background: var(--rule); overflow: hidden }
.p-bar .g, .k.g { background: var(--ink) }
.p-bar .a, .k.a { background: color-mix(in srgb, var(--ink) 40%, var(--bg)) }
.p-note { margin: 0; font: var(--font-ui-small); color: var(--muted) }
.k { display: inline-block; width: 8px; height: 8px; margin: 0 4px 0 0; vertical-align: 0 }
.k.a { margin-left: 6px }
.p-strip { position: relative; height: 16px; margin: 0 7px }
.p-strip::before { content: ""; position: absolute; inset: 50% 0 auto; height: 1px; background: var(--rule) }
.p-strip i { position: absolute; top: 50%; width: 8px; height: 8px; margin: -4px 0 0 -4px; border-radius: 50%; background: color-mix(in srgb, var(--ink) 28%, var(--bg)) }
.p-strip i.me { width: 14px; height: 14px; margin: -7px 0 0 -7px; background: var(--ink); box-shadow: 0 0 0 2px var(--card) }
.p-ends { margin: 0; display: flex; justify-content: space-between; font: var(--font-ui-small); color: var(--muted); font-variant-numeric: tabular-nums }
/* Tier 3: context, small and quiet */
.p-foot { display: grid; gap: 2px; padding-top: 10px; border-top: 1px solid var(--rule) }
.p-foot p { margin: 0; font: var(--font-ui-small); color: var(--muted) }
.p-foot b { color: var(--ink); font-weight: 650 }

.empty { color: var(--muted); font: var(--font-ui-small); margin: 0 }
footer { font: var(--font-ui-small); color: var(--muted); display: grid; gap: 8px; max-width: 65ch }
footer dl { margin: 0; display: grid; gap: 4px }
footer dt { font-weight: 700; color: var(--ink); display: inline }
footer dd { margin: 0; display: inline }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth } }
"""

FONTS = ("https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=EB+Garamond:wght@400..800"
         "&family=Fira+Sans:wght@400;500;600;700&family=Fira+Mono:wght@400;500;700&display=swap")


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


HOT_LAST5 = 3  # goals + assists in the last five matches that mark a player as in form


def _int(n):
    return f"{n:,}".replace(",", " ")


def _player_card(team, p):
    """Three tiers: the number that makes the player key (big), current form (medium), the rest (small, muted)."""
    meta = [team["name"]] + ([POSITIONS.get(p["position"])] if POSITIONS.get(p["position"]) else [])
    meta += [f'nr. {p["shirtNumber"]}'] if p.get("shirtNumber") else []
    played = (team.get("overall") or {}).get("p")
    scorer = bool(p["goals"] or p["assists"])

    # Goals and assists always read {goals}({penalties})+{assists}
    if scorer:
        hero = (f'<b aria-label="{p["goals"]} mål, {p["penalties"]} på straffe, {p["assists"]} målgivende">'
                f'{p["goals"]}<small>({p["penalties"]})</small><em>+{p["assists"]}</em></b>'
                f'<span>mål (straffe) + målgivende</span>')
    else:
        hero = f'<b>{p["starts"]}</b><span>{f"av {played} kamper fra start" if played else "kamper fra start"}</span>'

    form = ""
    if scorer:
        last5 = p["last5Goals"] + p["last5Assists"]
        tone = " hot" if last5 >= HOT_LAST5 else " cold" if not last5 and p["goals"] + p["assists"] >= KEY_MIN_CONTRIBUTIONS else ""
        flag = "<em>i form</em>" if tone == " hot" else ""
        form = (f'<p class="p-form{tone}"><span>Siste 5</span>'
                f'<b aria-label="{p["last5Goals"]} mål, {p["last5Assists"]} målgivende">{p["last5Goals"]}+{p["last5Assists"]}</b>{flag}</p>')

    fine = [f'{p["apps"]} kamper' + (f', {p["starts"]} fra start' if scorer else ""), f'{_int(p["minutes"])} min']
    if p["yellows"] or p["reds"]:
        fine.append(", ".join(t for n, t in ((p["yellows"], f'{p["yellows"]} gule'), (p["reds"], f'{p["reds"]} rødt')) if n))
    if p.get("avgRatingLast5"):
        fine.append(f'karakter siste 5: {_dec(p["avgRatingLast5"])}')
    sr, n = p.get("seasonRating"), stars(p.get("seasonRating"))
    rating = (f'FotMob-snitt <b>{_dec(sr["rating"], 2)}</b> · nr. {sr["rank"]} av {sr["of"]} i {escape(sr["league"])}'
              if sr else "For få minutter til FotMob-rating i ligaen")

    st = p.get("status")
    badge = f'<span class="p-status s-{st["kind"]}">{STATUS[st["kind"]]}</span>' if st else ""
    # FotMob's reason is sometimes just the status again («utestengt»); the badge already says that
    why = (f'<p class="p-why">{escape(st["reason"][:1].upper() + st["reason"][1:])}.</p>'
           if st and st.get("reason") and st["reason"].strip(". ").lower() != STATUS[st["kind"]].lower() else "")
    league = escape(team["league"]["name"]) if team.get("league") else "serien"
    star_html = (f'<span class="p-stars" role="img" aria-label="{n} av 3 stjerner">{"★" * n}<span class="off">{"★" * (3 - n)}</span></span>'
                 if n else "")
    return (f'<div class="player"><div class="p-head"><div class="p-top"><span class="p-name">{escape(p["name"])}</span>{star_html}</div>'
            f'<span class="p-meta">{escape(" · ".join(meta))}</span>{badge}{why}</div>'
            f'<div class="p-hero" aria-label="Tall fra {league}">{hero}</div>{form}{_team_role(team, p)}'
            f'<div class="p-foot"><p>{" · ".join(fine)}</p><p>{rating}</p></div></div>')


def _team_role(team, p):
    """How much the team leans on the player: share of the team's league goals, and FotMob rating against teammates."""
    blocks = []
    gf = (team.get("overall") or {}).get("gf")
    if gf and (p["goals"] or p["assists"]):
        involved = p["goals"] + p["assists"]
        lead, label = ((f'{round(100 * p["goals"] / gf)}\u202f%', f"av lagets {gf} seriemål") if p["goals"] else
                       (f'{round(100 * involved / gf)}\u202f%', f"av lagets {gf} seriemål kom etter målgivende"))
        note = (f'<p class="p-note"><span class="k g"></span>{p["goals"]} mål <span class="k a"></span>{p["assists"]} målgivende'
                f' · med på {round(100 * involved / gf)} %</p>' if p["goals"] and p["assists"] else "")
        blocks.append(
            f'<div class="p-role"><p class="p-big"><b>{lead}</b><span>{label}</span></p>'
            f'<div class="p-bar" role="img" aria-label="{p["goals"]} mål og {p["assists"]} målgivende av lagets {gf} mål">'
            f'<i class="g" style="width:{100 * p["goals"] / gf:.1f}%"></i><i class="a" style="width:{100 * p["assists"] / gf:.1f}%"></i></div>'
            f'{note}</div>')

    sr = p.get("seasonRating")
    mates = [q["seasonRating"]["rating"] for q in team.get("players") or [] if q.get("seasonRating")]
    if sr and len(mates) > 1:
        rank = 1 + sum(r > sr["rating"] for r in mates)
        lo, hi = min(mates), max(mates)
        pos = lambda r: 100 * (r - lo) / (hi - lo) if hi > lo else 50
        dots = "".join(f'<i style="left:{pos(r):.1f}%"></i>' for r in mates if r != sr["rating"])
        blocks.append(
            f'<div class="p-role"><p class="p-big"><b><small>nr.</small>{rank}</b><span>av {len(mates)} i {escape(team["name"])} på FotMob-snitt</span></p>'
            f'<div class="p-strip" role="img" aria-label="FotMob-snitt {_dec(sr["rating"], 2)}, lagkameratene fra {_dec(lo, 2)} til {_dec(hi, 2)}">'
            f'{dots}<i class="me" style="left:{pos(sr["rating"]):.1f}%"></i></div>'
            f'<p class="p-ends"><span>{_dec(lo, 2)}</span><span>{_dec(hi, 2)}</span></p></div>')
    if not blocks:
        return ""
    return f'<section class="p-team"><h4>Betydning for {escape(team["name"])}</h4>{"".join(blocks)}</section>'


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
        verdict = f'<div class="verdict"><span>Vår anbefaling</span><span class="marks">{marks}</span><span>{KIND[len(t)]}</span>{bomb_txt}</div>'
    return f"""
<article class="match" id="kamp-{idx}">{head}
  <p class="headline">{escape(a["headline"])}</p>
  <div class="take">{take}</div>
  <div class="reads">
    {_reads("signal", "Tallene som støtter folket", a.get("signal"))}
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
        names = {1: ("sikker", "sikre"), 2: ("halvgardering", "halvgarderinger"), 3: ("helgardering", "helgarderinger")}
        parts = [f"{n} {names[k][n != 1]}" for k, n in counts.items() if n]
        legend = (f'<p class="legend">Tallene er folkets prosent. Markerte ruter er vår anbefaling, regnet fra oddsen: {", ".join(parts)}, '
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
<meta name="color-scheme" content="dark light">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
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
      <div><dt>Effektivitet</dt> <dd>hvor mange mål et lag scorer, sammenlignet med hvor mange sjansene vanligvis gir. Langt over eller under pleier å jevne seg ut.</dd></div>
      <div><dt>Oddsen</dt> <dd>oddsen fra Norsk Tippings Oddsen, regnet om til sannsynlighet uten bookmakerens margin. Innrammede tall er tegn der oddsen ligger minst {VALUE_GAP} prosentpoeng over folkets fordeling.</dd></div>
      <div><dt>Vår anbefaling</dt> <dd>sikker når oddsen gir favoritten minst {SPIKE_AT} %. Ellers halvgardering med tegn over {KEEP_AT} % og tegnene folket undervurderer mest i forhold til oddsen.</dd></div>
      <div><dt>Stjerner</dt> <dd>nøkkelspillerens plass blant alle spillere i ligaen på FotMobs snittkarakter for sesongen: ★★★ topp 15 %, ★★ topp halvdel, ★ resten.</dd></div>
      <div><dt>Bombe</dt> <dd>et tegn folket gir under {BOMB_BELOW} %. Systemet har minst {MIN_BOMBS}. Mangler det bomber, legges de på de sikre kampene der oddsen ligger mest over folket, og halvgarderingen med det svakeste tegnet blir sikker, slik at antallet rekker er det samme.</dd></div>
    </dl>
    <span>Statistikk fra NIFS, folkets fordeling og odds fra Norsk Tipping. Hentet {datetime.now(ZoneInfo("Europe/Oslo")).strftime("%d.%m.%Y %H.%M")}. Skader og utestengelser fra FotMob. Karantenefare er beregnet fra gule kort i NIFS etter seriens regler.</span>
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
