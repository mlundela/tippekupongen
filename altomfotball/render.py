"""Render a coupon page (Norwegian, phone-first) from coupons/<id>/facts.json + analysis.json."""

import json
from datetime import datetime
from html import escape
from pathlib import Path

WEEKDAYS = ["man.", "tir.", "ons.", "tor.", "fre.", "lør.", "søn."]
MONTHS = ["januar", "februar", "mars", "april", "mai", "juni", "juli", "august",
          "september", "oktober", "november", "desember"]
OUTCOME = {"V": ("V", "Seier"), "U": ("U", "Uavgjort"), "T": ("T", "Tap")}
ABSENCE = {"suspended": "Utestengt", "card_risk": "Karantenefare", "missing": "Ute av troppen", "returning": "Tilbake"}
BUCKETS = ("0-15", "16-30", "31-45", "46-60", "61-75", "76-90")

CSS = """
/* Layout: one column of coupon rows; each match is a slip with the analysis up front and the numbers behind a toggle. */
:root {
  --paper: #f2f5f3; --slip: #ffffff; --ink: #15222b; --muted: #5a6a71; --rule: #d3ddd8;
  --pitch: #0d6a4e; --pen: #2445c4; --pen-soft: #e3e8fb;
  --win: #1b7a43; --draw: #b07a12; --loss: #b8322f;
  --display: "Archivo", "Arial Narrow", system-ui, sans-serif;
  --body: "Source Serif 4", Georgia, "Times New Roman", serif;
  --ui: "Archivo", system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #0f1619; --slip: #172126; --ink: #e6eeea; --muted: #93a4a9; --rule: #2a383d;
  --pitch: #4cc79a; --pen: #8ea2ff; --pen-soft: #222c52;
  --win: #4fc27f; --draw: #e0aa45; --loss: #f07a72; color-scheme: dark } }
:root[data-theme="dark"] {
  --paper: #0f1619; --slip: #172126; --ink: #e6eeea; --muted: #93a4a9; --rule: #2a383d;
  --pitch: #4cc79a; --pen: #8ea2ff; --pen-soft: #222c52;
  --win: #4fc27f; --draw: #e0aa45; --loss: #f07a72; color-scheme: dark }

* { box-sizing: border-box }
body { margin: 0; background: var(--paper); color: var(--ink); font: 400 16px/1.5 var(--ui);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 20px 48px; -webkit-text-size-adjust: 100% }
.wrap { max-width: 640px; margin: 0 auto; display: grid; gap: 20px }
a { color: inherit }
.num { font-variant-numeric: tabular-nums }

header.top { display: grid; gap: 6px }
.eyebrow { font: 600 12px/1 var(--ui); letter-spacing: .12em; text-transform: uppercase; color: var(--pitch) }
h1 { margin: 0; font: 800 clamp(34px, 9vw, 48px)/.95 var(--display); font-stretch: 75%; letter-spacing: -.01em; text-wrap: balance }
.meta { display: flex; flex-wrap: wrap; gap: 4px 16px; color: var(--muted); font-size: 14px }
.meta b { color: var(--ink); font-weight: 600 }

/* Coupon overview: a printed slip with pen marks */
.slip { background: var(--slip); border: 1px solid var(--rule); border-radius: 6px; overflow: hidden }
.slip-head, .slip-row { display: grid; grid-template-columns: 28px minmax(0, 1fr) repeat(3, 34px); align-items: center; gap: 0 4px; padding: 0 10px }
.slip-head { font: 600 11px/1 var(--ui); letter-spacing: .1em; color: var(--muted); padding-block: 10px 6px; border-bottom: 1px solid var(--rule) }
.slip-head span:nth-child(n+3) { text-align: center }
.slip-row { min-height: 44px; border-bottom: 1px dashed var(--rule); text-decoration: none }
.slip-row:last-child { border-bottom: 0 }
.slip-row:focus-visible { outline: 2px solid var(--pen); outline-offset: -2px }
.slip-no { font: 700 15px/1 var(--display); color: var(--muted) }
.slip-name { font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.box { justify-self: center; width: 26px; height: 26px; border: 1.5px solid var(--rule); border-radius: 4px;
  display: grid; place-items: center; font: 700 12px/1 var(--ui); color: var(--muted) }
.box.on { border-color: var(--pen); background: var(--pen-soft); color: var(--pen) }
.box.on::after { content: "✕"; font-size: 15px }
.box.on span { display: none }
.legend { font-size: 13px; color: var(--muted); margin: 0 }

/* Match slip */
article.match { background: var(--slip); border: 1px solid var(--rule); border-radius: 6px; display: grid; gap: 14px; padding: 16px; scroll-margin-top: 12px }
.m-head { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 2px 12px; align-items: start }
.m-no { grid-row: span 2; font: 800 40px/.9 var(--display); font-stretch: 75%; color: var(--pitch); min-width: 1.4ch }
.m-teams { margin: 0; font: 750 24px/1.1 var(--display); font-stretch: 85%; text-wrap: balance }
.m-teams .vs { color: var(--muted); font-weight: 400 }
.m-sub { color: var(--muted); font-size: 13px }
.headline { margin: 0; font: 600 18px/1.35 var(--body) }
.summary { margin: 0; font: 400 16.5px/1.6 var(--body); max-width: 65ch }
.facts { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px }
.facts li { display: grid; grid-template-columns: 14px minmax(0, 1fr); gap: 8px; font-size: 15px; line-height: 1.45 }
.facts li::before { content: ""; width: 6px; height: 6px; margin-top: .55em; border-radius: 50%; background: var(--pitch) }

/* Tips */
.tips { display: grid; gap: 6px }
.tip-row { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 8px; align-items: center; font-size: 12px; color: var(--muted) }
.bar { display: flex; height: 22px; border-radius: 3px; overflow: hidden; font: 600 11px/22px var(--ui) }
.bar span { text-align: center; color: var(--slip); white-space: nowrap; overflow: hidden; min-width: 0 }
.bar .h { background: var(--pitch) } .bar .u { background: var(--muted) } .bar .b { background: var(--ink) }
.tendens { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted) }
.tendens .marks { display: flex; gap: 4px }
.tendens .mark { width: 26px; height: 26px; border-radius: 50%; border: 2px solid var(--pen); color: var(--pen); display: grid; place-items: center; font: 700 13px/1 var(--ui) }

/* Stats drawer */
details { border-top: 1px solid var(--rule); padding-top: 10px }
summary { cursor: pointer; font: 600 14px/1 var(--ui); color: var(--pitch); padding-block: 6px; list-style: none }
summary::-webkit-details-marker { display: none }
summary::before { content: "+ "; } details[open] summary::before { content: "− "; }
summary:focus-visible { outline: 2px solid var(--pen); outline-offset: 2px }
.stats { display: grid; gap: 18px; padding-top: 10px }
.block h3 { margin: 0 0 8px; font: 600 11px/1 var(--ui); letter-spacing: .12em; text-transform: uppercase; color: var(--muted) }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px }
.two > div { min-width: 0 }
.team-label { font: 700 14px/1.2 var(--ui); margin-bottom: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.kv { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 8px; font-size: 13.5px }
.kv dt { color: var(--muted) } .kv dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums }
.chips { display: flex; gap: 4px; flex-wrap: wrap }
.chip { width: 30px; display: grid; justify-items: center; gap: 2px }
.chip b { width: 24px; height: 24px; border-radius: 4px; display: grid; place-items: center; color: var(--slip); font: 700 12px/1 var(--ui) }
.chip small { font-size: 10px; color: var(--muted); font-variant-numeric: tabular-nums }
.o-V b { background: var(--win) } .o-U b { background: var(--draw) } .o-T b { background: var(--loss) }
.form-list { margin: 6px 0 0; padding: 0; list-style: none; font-size: 12.5px; color: var(--muted); display: grid; gap: 1px }
.form-list b { color: var(--ink); font-weight: 600; font-variant-numeric: tabular-nums }
.timing { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 3px; align-items: end }
.timing .col { display: grid; gap: 2px; justify-items: center }
.timing .stack { width: 100%; height: 56px; display: flex; flex-direction: column; justify-content: flex-end; gap: 1px }
.timing .for { background: var(--pitch); border-radius: 2px 2px 0 0 }
.timing .against { background: var(--loss); opacity: .8 }
.timing small { font-size: 9.5px; color: var(--muted); font-variant-numeric: tabular-nums }
.key { display: flex; gap: 12px; font-size: 11.5px; color: var(--muted); margin-top: 6px }
.key i { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 4px; vertical-align: -1px }
table { border-collapse: collapse; width: 100%; font-size: 13px; font-variant-numeric: tabular-nums }
.scroll { overflow-x: auto }
th { text-align: left; font-weight: 600; color: var(--muted); font-size: 11px; letter-spacing: .06em; text-transform: uppercase; padding: 4px 6px 4px 0 }
td { padding: 5px 6px 5px 0; border-top: 1px solid var(--rule); vertical-align: top }
td.r, th.r { text-align: right }
.people { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; font-size: 13.5px }
.people li { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px }
.people .n { overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
.people .s { color: var(--muted); font-variant-numeric: tabular-nums; font-size: 12.5px }
.badge { display: inline-block; font: 600 10.5px/1 var(--ui); letter-spacing: .04em; padding: 3px 5px; border-radius: 3px; margin-right: 6px; border: 1px solid currentColor }
.k-suspended { color: var(--loss) } .k-card_risk { color: var(--draw) } .k-missing { color: var(--muted) } .k-returning { color: var(--win) }
.empty { color: var(--muted); font-size: 13px; margin: 0 }
.note { font-size: 12.5px; color: var(--muted); margin: 0; max-width: 65ch }
footer { font-size: 12.5px; color: var(--muted); display: grid; gap: 6px }
@media (max-width: 380px) { .two { grid-template-columns: 1fr } }
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


def _date_short(iso):
    d = datetime.fromisoformat(iso)
    return f"{d.day}.{d.month}.{str(d.year)[2:]}"


def _nok(amount):
    v = float(amount)
    return f"{v / 1e6:.2f}".replace(".", ",") + " mill. kr" if v >= 1e6 else f"{round(v):,}".replace(",", " ") + " kr"


def _rec(r):
    if not r or not r.get("p"):
        return "–"
    return f"{r['v']}-{r['u']}-{r['t']}"


def _tip_bar(t):
    return (f'<div class="bar" role="img" aria-label="H {t["home"]} %, U {t["draw"]} %, B {t["away"]} %">'
            f'<span class="h" style="width:{t["home"]}%">H {t["home"]}</span>'
            f'<span class="u" style="width:{t["draw"]}%">U {t["draw"]}</span>'
            f'<span class="b" style="width:{t["away"]}%">B {t["away"]}</span></div>')


def _form_chips(form):
    if not form:
        return '<p class="empty">Ingen kamper funnet.</p>'
    chips = "".join(
        f'<span class="chip o-{f["outcome"]}" title="{escape(f["opponent"])}">'
        f'<b>{f["outcome"]}</b><small>{f["gf"]}–{f["ga"]}</small></span>' for f in form)
    rows = "".join(
        f'<li>{_date_short(f["date"])} {"H" if f["home"] else "B"} mot {escape(f["opponent"])} <b>{f["gf"]}–{f["ga"]}</b></li>'
        for f in reversed(form))
    return (f'<div class="chips" aria-label="Siste kamper, eldste først">{chips}</div>'
            f'<ul class="form-list" aria-label="Nyeste først">{rows}</ul>')


def _table_block(h, a):
    rows = []
    for t in (h, a):
        tb = t.get("table")
        if not tb:
            continue
        rows.append(
            f'<tr><td>{escape(t["name"])}</td><td class="r">{tb["place"]}.</td><td class="r">{tb["played"]}</td>'
            f'<td class="r">{_rec(t.get("overall"))}</td><td class="r">{tb["gf"]}–{tb["ga"]}</td><td class="r"><b>{tb["points"]}</b></td></tr>')
    if not rows:
        return ""
    of = (h.get("table") or a.get("table"))["of"]
    return (f'<div class="block"><h3>Tabellen</h3><div class="scroll"><table><thead><tr><th>Lag</th><th class="r">Pl.</th>'
            f'<th class="r">K</th><th class="r">V-U-T</th><th class="r">Mål</th><th class="r">P</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'<p class="note">Av {of} lag. Angrep og forsvar er rangert etter scorede og innslupne mål i serien.</p></div>')


def _kv(pairs):
    return '<dl class="kv">' + "".join(f"<dt>{escape(k)}</dt><dd>{v}</dd>" for k, v in pairs if v is not None) + "</dl>"


def _team_numbers(t, venue):
    tb, rec = t.get("table") or {}, t.get(venue) or {}
    av = t.get("averages") or {}
    venue_label = "Hjemme" if venue == "homeRecord" else "Borte"
    pairs = [
        (f"{venue_label} (V-U-T)", _rec(rec)),
        (f"{venue_label}, mål", f'{rec.get("gf", 0)}–{rec.get("ga", 0)}' if rec.get("p") else None),
        (f"{venue_label}, poeng per kamp", str(rec["ppg"]).replace(".", ",") if rec.get("ppg") is not None else None),
        ("Angrep (rangering)", f'{tb["attackRank"]}.' if tb else None),
        ("Forsvar (rangering)", f'{tb["defenceRank"]}.' if tb else None),
        ("Holdt nullen", t.get("cleanSheets")),
        ("Ikke scoret", t.get("failedToScore")),
        ("Mistet ledelse", t.get("ledNotWon")),
        ("Snudd til seier", t.get("cameFromBehind")),
        ("xG for / mot", f'{av["xg"]:.2f} / {av["xgAgainst"]:.2f}'.replace(".", ",") if "xg" in av and "xgAgainst" in av else None),
        ("Skudd per kamp", f'{av["totalShots"]:.1f}'.replace(".", ",") if "totalShots" in av else None),
        ("Ballinnehav", f'{av["possession"]:.0f} %' if "possession" in av else None),
        ("Trener", escape(t["coach"]) if t.get("coach") else None),
    ]
    return f'<div><div class="team-label">{escape(t["name"])}</div>{_kv(pairs)}</div>'


def _timing(t):
    gt = t.get("goalTiming")
    if not gt:
        return ""
    peak = max(max(gt["scored"].values()), max(gt["conceded"].values()), 1)
    cols = "".join(
        f'<div class="col"><div class="stack">'
        f'<div class="for" style="height:{gt["scored"][b] / peak * 100:.0f}%" title="Scoret {gt["scored"][b]}"></div>'
        f'<div class="against" style="height:{gt["conceded"][b] / peak * 100:.0f}%" title="Sluppet inn {gt["conceded"][b]}"></div>'
        f'</div><small>{gt["scored"][b]}/{gt["conceded"][b]}</small><small>{b}</small></div>' for b in BUCKETS)
    return f'<div><div class="team-label">{escape(t["name"])}</div><div class="timing">{cols}</div></div>'


def _players(t):
    rows = []
    for p in t.get("inForm") or t.get("topContributors") or []:
        rating = f' · snitt {p["avgRatingLast5"]:.1f}'.replace(".", ",") if p.get("avgRatingLast5") else ""
        pens = f' ({p["penalties"]} str.)' if p.get("penalties") else ""
        rows.append(f'<li><span class="n">{escape(p["name"])}</span>'
                    f'<span class="s">siste 5: {p["last5Goals"]}+{p["last5Assists"]} · sesong: {p["goals"]}{pens}+{p["assists"]}{rating}</span></li>')
    body = f'<ul class="people">{"".join(rows)}</ul>' if rows else '<p class="empty">Ingen mål eller målgivende i serien ennå.</p>'
    return f'<div><div class="team-label">{escape(t["name"])}</div>{body}</div>'


def _absences(t):
    items = t.get("absences") or []
    order = ("suspended", "card_risk", "missing", "returning")
    items = sorted(items, key=lambda x: order.index(x["kind"]))
    if not items:
        return f'<div><div class="team-label">{escape(t["name"])}</div><p class="empty">Ingen kjente.</p></div>'
    risk = [x for x in items if x["kind"] == "card_risk"]
    rows = "".join(
        f'<li><span class="n"><span class="badge k-{x["kind"]}">{ABSENCE[x["kind"]]}</span>{escape(x["name"])}</span>'
        f'<span class="s">{escape(x["reason"])}</span></li>' for x in items if x["kind"] != "card_risk")
    if risk:
        names = ", ".join(escape(x["name"]) for x in risk)
        rows += (f'<li><span class="n"><span class="badge k-card_risk">{ABSENCE["card_risk"]}</span>{names}</span>'
                 f'<span class="s">ett gult kort fra karantene</span></li>')
    return f'<div><div class="team-label">{escape(t["name"])}</div><ul class="people">{rows}</ul></div>'


def _h2h(f):
    h2h = f["h2h"]
    ms = h2h["meetings"]
    if not ms:
        return '<div class="block"><h3>Innbyrdes</h3><p class="empty">Lagene har ikke møttes i kamper NIFS har registrert.</p></div>'
    home = f["home"]["name"]
    rows = "".join(
        f'<tr><td>{_date_short(m["date"])}</td><td>{escape(home) if m["home"] else escape(m["opponent"])} – '
        f'{escape(m["opponent"]) if m["home"] else escape(home)}</td>'
        f'<td class="r"><b>{(m["gf"] if m["home"] else m["ga"])}–{(m["ga"] if m["home"] else m["gf"])}</b></td>'
        f'<td>{escape(m["competition"])}</td></tr>' for m in reversed(ms))
    r = h2h["record"]
    return (f'<div class="block"><h3>Innbyrdes</h3>'
            f'<p class="note">Siste {r["p"]} møter, sett fra {escape(home)}: {r["v"]} seire, {r["u"]} uavgjort, {r["t"]} tap.</p>'
            f'<div class="scroll"><table><thead><tr><th>Dato</th><th>Kamp</th><th class="r">Res.</th><th>Turnering</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></div>')


def _match(f, a, idx):
    h, aw = f["home"], f["away"]
    tips = f["nt"]["tips"]["fullTime"]
    tendens = (a or {}).get("tendens", "")
    marks = "".join(f'<span class="mark">{c}</span>' for c in tendens)
    round_txt = f', {f["round"]}. runde' if f.get("round") else ""
    analysis_html = ""
    if a:
        bullets = "".join(f"<li>{escape(b)}</li>" for b in a.get("facts", []))
        analysis_html = (f'<p class="headline">{escape(a["headline"])}</p>'
                         f'<p class="summary">{escape(a["summary"])}</p>'
                         f'<ul class="facts">{bullets}</ul>')
    else:
        analysis_html = '<p class="empty">Analysen er ikke skrevet ennå.</p>'
    return f"""
<article class="match" id="kamp-{idx}">
  <div class="m-head">
    <span class="m-no num">{idx}</span>
    <h2 class="m-teams">{escape(h["name"])} <span class="vs">–</span> {escape(aw["name"])}</h2>
    <div class="m-sub">{_kick(f["kickoff"])} · {escape(f["competition"])}{round_txt}{(" · " + escape(f["stadium"])) if f.get("stadium") else ""}</div>
  </div>
  {analysis_html}
  <div class="tips">
    <div class="tip-row"><span>Folket</span>{_tip_bar(tips["peoples"])}</div>
    <div class="tip-row"><span>Ekspertene</span>{_tip_bar(tips["expert"])}</div>
    {f'<div class="tendens"><span>Vår tendens</span><span class="marks">{marks}</span><span>{["", "spik", "halvgardering", "helgardering"][len(tendens)]}</span></div>' if tendens else ""}
  </div>
  <details>
    <summary>Se statistikken</summary>
    <div class="stats">
      {_table_block(h, aw)}
      <div class="block"><h3>Form, alle turneringer</h3><div class="two"><div><div class="team-label">{escape(h["name"])}</div>{_form_chips(h.get("form"))}</div><div><div class="team-label">{escape(aw["name"])}</div>{_form_chips(aw.get("form"))}</div></div></div>
      <div class="block"><h3>Hjemme mot borte</h3><div class="two">{_team_numbers(h, "homeRecord")}{_team_numbers(aw, "awayRecord")}</div></div>
      <div class="block"><h3>Når målene kommer (scoret/sluppet inn)</h3><div class="two">{_timing(h)}{_timing(aw)}</div>
        <div class="key"><span><i style="background:var(--pitch)"></i>Scoret</span><span><i style="background:var(--loss)"></i>Sluppet inn</span><span>per kvarter, serien</span></div></div>
      {_h2h(f)}
      <div class="block"><h3>Spillere i form</h3><div class="two">{_players(h)}{_players(aw)}</div>
        <p class="note">Mål+målgivende i de fem siste seriekampene{", med snittkarakter der NIFS har spillerbørs" if h.get("bestRated") or aw.get("bestRated") else ""}.</p></div>
      <div class="block"><h3>Mulig fravær</h3><div class="two">{_absences(h)}{_absences(aw)}</div>
        <p class="note">Beregnet fra kort og tropper i NIFS, ikke offisielle lister. Skader meldes ikke i dataene; «ute av troppen» betyr at en fast starter manglet i forrige kamp.</p></div>
    </div>
  </details>
</article>"""


def render(coupon_dir, site_dir, fragment_path=None):
    facts = json.loads((coupon_dir / "facts.json").read_text())
    analysis_file = coupon_dir / "analysis.json"
    analysis = json.loads(analysis_file.read_text()) if analysis_file.exists() else {}
    c = facts["coupon"]
    matches = sorted(facts["matches"], key=lambda m: m["nt"]["line"])
    first = min(m["kickoff"] for m in matches)

    rows = []
    for m in matches:
        a = analysis.get(str(m["nt"]["eventId"])) or {}
        t = a.get("tendens", "")
        boxes = "".join(f'<span class="box{" on" if s in t else ""}"><span>{s}</span></span>' for s in "HUB")
        rows.append(f'<a class="slip-row" href="#kamp-{m["nt"]["line"]}"><span class="slip-no num">{m["nt"]["line"]}</span>'
                    f'<span class="slip-name">{escape(m["home"]["name"])} – {escape(m["away"]["name"])}</span>{boxes}</a>')

    picks = [(analysis.get(str(m["nt"]["eventId"])) or {}).get("tendens", "") for m in matches]
    system = ""
    if all(picks):
        n_rows = 1
        for p in picks:
            n_rows *= len(p)
        counts = {k: sum(len(p) == k for p in picks) for k in (1, 2, 3)}
        parts = [f"{counts[1]} spiker"] if counts[1] else []
        parts += [f"{counts[2]} halvgarderinger"] if counts[2] else []
        parts += [f"{counts[3]} helgarderinger"] if counts[3] else []
        system = (f'<p class="legend">Kryssene er vår tendens: {", ".join(parts)}. Spilt som system blir det '
                  f'<b class="num">{n_rows}</b> rekker ({_nok(n_rows)} med 1 kr per rekke). Trykk på en kamp for analysen.</p>')
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
  <nav class="slip" aria-label="Kupongen">
    <div class="slip-head"><span>NR</span><span>KAMP</span><span>H</span><span>U</span><span>B</span></div>
    {"".join(rows)}
  </nav>
  {system or '<p class="legend">Trykk på en kamp for analysen.</p>'}
  {"".join(_match(m, analysis.get(str(m["nt"]["eventId"])), m["nt"]["line"]) for m in matches)}
  <footer>
    <span>Statistikk fra NIFS, tips og prosenter fra Norsk Tipping. Hentet {datetime.now().strftime("%d.%m.%Y %H.%M")}.</span>
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
