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
.player { border: 1px solid var(--rule); border-radius: 6px; padding: 14px; display: grid; gap: 14px; align-content: start; background: var(--paper); min-width: 0 }
.p-head { display: grid; gap: 3px }
.p-name { font: 700 16px/1.2 var(--display); font-stretch: 90% }
.p-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px }
.p-stars { font-size: 15px; letter-spacing: 1px; color: var(--pen); white-space: nowrap }
.p-stars .off { color: var(--rule) }
.p-meta { font-size: 12.5px; color: var(--muted) }
.p-status { justify-self: start; margin-top: 6px; font: 600 11px/1 var(--ui); letter-spacing: .04em; padding: 4px 6px; border-radius: 3px; border: 1px solid currentColor }
.p-status.s-suspended, .p-status.s-injured, .p-status.s-missing { color: var(--warn) }
.p-status.s-doubtful { color: var(--ink) }
.p-status.s-returning { color: var(--pitch) }
.p-status.s-card_risk { color: var(--muted) }
.p-why { font-size: 12.5px; line-height: 1.4; color: var(--muted); margin: 2px 0 0 }
/* Tier 1: what makes the player key. The lead number is big; the rest sit on its baseline, smaller. */
.p-hero { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 6px 20px }
.p-hero div { display: grid; gap: 4px; min-width: 0 }
.p-hero b { font: 700 22px/1 var(--ui); font-variant-numeric: tabular-nums; letter-spacing: -.01em }
.p-hero .lead b { font-size: 40px; font-weight: 800; letter-spacing: -.035em }
.p-hero span { font-size: 11.5px; line-height: 1.2; color: var(--muted) }
.p-hero small { font-size: inherit; opacity: .8 }
.p-hero .zero b { color: var(--muted); font-weight: 500 }
/* Tier 2: form. Hot form takes the accent; no goals or assists in five fades. */
.p-form { margin: 0; display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 8px; font-size: 12px; color: var(--muted) }
.p-form b { font: 650 15px/1.2 var(--ui); color: var(--ink) }
.p-form.hot b { color: var(--pitch); font-weight: 750 }
.p-form.cold b { color: var(--muted); font-weight: 500 }
.p-form em { font: 700 10.5px/1 var(--ui); font-style: normal; letter-spacing: .08em; text-transform: uppercase; color: var(--pitch);
  border: 1px solid currentColor; border-radius: 3px; padding: 3px 5px }
/* Tier 3: context, small and quiet */
.p-foot { display: grid; gap: 2px; padding-top: 10px; border-top: 1px solid var(--rule) }
.p-foot p { margin: 0; font-size: 12px; line-height: 1.45; color: var(--muted) }
.p-foot b { color: var(--ink); font-weight: 650 }

.empty { color: var(--muted); font-size: 14px; margin: 0 }
footer { font-size: 12.5px; color: var(--muted); display: grid; gap: 8px; max-width: 65ch }
footer dl { margin: 0; display: grid; gap: 4px }
footer dt { font-weight: 700; color: var(--ink); display: inline }
footer dd { margin: 0; display: inline }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth } }

/* Theme picker */
.skins { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; margin-top: 8px; max-width: 440px }
.skins button { display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 36px; padding: 0 6px; border: 1px solid var(--rule); border-radius: 999px;
  background: transparent; color: var(--ink); font: 600 12.5px/1 var(--ui); cursor: pointer; white-space: nowrap }
.skins button[aria-pressed="true"] { border-color: var(--ink); background: var(--pen-soft) }
.skins button:focus-visible { outline: 2px solid var(--pen); outline-offset: 2px }
.sw { flex: none; width: 14px; height: 14px; border-radius: 50%; box-shadow: 0 0 0 1px var(--rule) }
"""

# Themes besides the default: three colours each (background, ink, accent) and their own type.
# Every other shade on the page is a mix of those three. Picked on the page, remembered per browser.
SKINS = {
    "klassisk": ("Klassisk", ("#f2f5f3", "#15222b", "#0d6a4e"), None),
    "flomlys": ("Flomlys", ("#0e0f0c", "#f1efe6", "#c6ff3d"),
                ('"Unbounded", system-ui, sans-serif', '"Manrope", system-ui, sans-serif', '"JetBrains Mono", ui-monospace, monospace', "dark")),
    "papir": ("Papir", ("#f4f1ea", "#1a1a1a", "#cf3a1d"),
              ('"Instrument Serif", Georgia, serif', '"Geist", system-ui, sans-serif', '"Geist Mono", ui-monospace, monospace', "light")),
    "kobolt": ("Kobolt", ("#2a3cff", "#f7f5ee", "#ffd23f"),
               ('"Bricolage Grotesque", system-ui, sans-serif', '"Schibsted Grotesk", system-ui, sans-serif', '"Schibsted Grotesk", system-ui, sans-serif', "dark")),
}

SKIN_CSS = "".join(
    f':root[data-skin="{key}"] {{ --bg: {bg}; --fg: {fg}; --accent: {accent}; --display: {display}; '
    f'--body: {body}; --ui: {body}; --num: {num}; color-scheme: {scheme} }}\n'
    for key, (_, (bg, fg, accent), fonts) in SKINS.items() if fonts for display, body, num, scheme in [fonts]) + """
:root[data-skin] {
  --paper: var(--bg); --ink: var(--fg); --slip: color-mix(in srgb, var(--fg) 4%, var(--bg));
  --muted: color-mix(in srgb, var(--fg) 64%, var(--bg)); --rule: color-mix(in srgb, var(--fg) 20%, var(--bg));
  --pitch: var(--accent); --warn: var(--accent); --pen: var(--fg); --pen-soft: color-mix(in srgb, var(--fg) 12%, var(--bg)) }
/* With one accent, «støtter folket» is ink and «kan snu kampen» is the accent, dashed like the bombs */
:root[data-skin] .read.signal h3 { color: var(--ink) }
:root[data-skin] .read.signal li { border-left-color: var(--ink) }
:root[data-skin] .read.noise li { border-left-style: dashed }
:root[data-skin] :is(.box, .cell, .mark, .p-hero b, .p-form b, .read .stat, .odds, .slip-no) { font-family: var(--num) }
:root[data-skin] .box.on:not(.bomb) { background: var(--ink); color: var(--paper); border-color: var(--ink) }

/* Flomlys: night match under floodlights. Square edges, wide display type, volt accent. */
[data-skin="flomlys"] h1 { font: 800 clamp(22px, 6.4vw, 40px)/1.05 var(--display); text-transform: uppercase; letter-spacing: -.02em }
[data-skin="flomlys"] .intro h2 { font: 700 19px/1.25 var(--display); letter-spacing: -.01em }
[data-skin="flomlys"] .eyebrow { font-family: var(--num); letter-spacing: .06em }
[data-skin="flomlys"] :is(.slip, article.match, .player, .box, .cell, .p-status) { border-radius: 0 }
[data-skin="flomlys"] .box.on:not(.bomb) { background: var(--accent); border-color: var(--accent); color: var(--bg) }
[data-skin="flomlys"] .m-no { font: 800 32px/1 var(--display); color: var(--accent) }
[data-skin="flomlys"] .m-teams { font: 700 18px/1.25 var(--display); letter-spacing: -.01em }
[data-skin="flomlys"] .headline { font: 700 18px/1.4 var(--body) }
[data-skin="flomlys"] :is(.take p, .intro p) { font-size: 16px; line-height: 1.65 }
[data-skin="flomlys"] .p-name { font: 700 14px/1.3 var(--display) }
[data-skin="flomlys"] .p-hero .lead b { color: var(--accent); letter-spacing: -.06em }
[data-skin="flomlys"] .p-stars, [data-skin="flomlys"] .mark { color: var(--accent); border-color: var(--accent) }

/* Papir: the sports pages of a broadsheet. Big serif headlines, hairlines instead of boxes, one red. */
[data-skin="papir"] h1 { font: 400 clamp(46px, 13vw, 68px)/.92 var(--display); letter-spacing: -.015em }
[data-skin="papir"] .intro h2 { font: 400 italic 28px/1.1 var(--display) }
[data-skin="papir"] .slip { background: transparent; border: 0; border-top: 3px solid var(--ink); border-bottom: 1px solid var(--ink); border-radius: 0 }
[data-skin="papir"] article.match { background: transparent; border: 0; border-top: 3px solid var(--ink); border-radius: 0; padding: 14px 0 8px }
[data-skin="papir"] .m-no { font: 400 italic 54px/.85 var(--display); color: var(--accent) }
[data-skin="papir"] .m-teams { font: 400 32px/1.02 var(--display); letter-spacing: -.01em }
[data-skin="papir"] .m-teams .vs { font-style: italic }
[data-skin="papir"] .headline { font: 400 italic 23px/1.25 var(--display) }
[data-skin="papir"] :is(.take p, .intro p) { font-size: 16px; line-height: 1.65 }
[data-skin="papir"] :is(.player, .box, .cell, .p-status) { border-radius: 0 }
[data-skin="papir"] .player { background: transparent }
[data-skin="papir"] .p-name { font: 400 21px/1.1 var(--display) }
[data-skin="papir"] .p-hero b { font-family: var(--display); font-weight: 400; font-size: 28px; letter-spacing: 0 }
[data-skin="papir"] .p-hero .lead b { font-size: 54px; font-weight: 400; letter-spacing: -.02em }

/* Kobolt: a cobalt-blue match programme. Soft cards, pill marks, condensed heavy headlines. */
:root[data-skin="kobolt"] { --slip: color-mix(in srgb, var(--fg) 9%, var(--bg)) }
[data-skin="kobolt"] h1 { font: 800 clamp(42px, 12vw, 62px)/.88 var(--display); font-stretch: 75%; letter-spacing: -.03em }
[data-skin="kobolt"] .intro h2 { font: 800 24px/1.1 var(--display); font-stretch: 80%; letter-spacing: -.01em }
[data-skin="kobolt"] .eyebrow { color: var(--accent) }
[data-skin="kobolt"] :is(.slip, article.match) { border: 0; border-radius: 20px }
[data-skin="kobolt"] article.match { padding: 18px }
[data-skin="kobolt"] .player { border: 0; border-radius: 14px; background: color-mix(in srgb, var(--fg) 7%, var(--bg)) }
[data-skin="kobolt"] :is(.box, .cell, .p-status) { border-radius: 999px }
[data-skin="kobolt"] .m-no { font: 800 50px/.85 var(--display); font-stretch: 75%; color: var(--accent) }
[data-skin="kobolt"] .m-teams { font: 800 27px/1.02 var(--display); font-stretch: 80%; letter-spacing: -.02em }
[data-skin="kobolt"] .headline { font: 700 19px/1.35 var(--body) }
[data-skin="kobolt"] :is(.take p, .intro p) { font-size: 16.5px; line-height: 1.6 }
[data-skin="kobolt"] .read li { border-left-width: 3px }
/* Schibsted Grotesk's tabular figures space out commas and colons; keep them for the aligned boxes only */
[data-skin="kobolt"] :is(.read .stat, .odds) { font-variant-numeric: normal }
[data-skin="kobolt"] .p-name { font: 800 18px/1.15 var(--display); font-stretch: 85% }
[data-skin="kobolt"] .p-hero b { font-family: var(--display); font-weight: 800; font-stretch: 75% }
[data-skin="kobolt"] .p-hero .lead b { font-size: 50px; color: var(--accent) }
[data-skin="kobolt"] .p-stars, [data-skin="kobolt"] .mark { color: var(--accent); border-color: var(--accent) }
"""

FONTS = ("https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800"
         "&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Unbounded:wght@400..800&family=Manrope:wght@400..800"
         "&family=JetBrains+Mono:wght@400..700&family=Instrument+Serif:ital@0;1&family=Geist:wght@400..700"
         "&family=Geist+Mono:wght@400..700&family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,400..800"
         "&family=Schibsted+Grotesk:wght@400..800&display=swap")

SKIN_KEY = "altomfotball-tema"
# Runs before the page paints, so a remembered theme doesn't flash the default first
SKIN_BOOT = f"""<script>(function(){{try{{var s=localStorage.getItem("{SKIN_KEY}");if(s&&s!=="klassisk"&&{json.dumps(list(SKINS))}.indexOf(s)>=0)document.documentElement.setAttribute("data-skin",s)}}catch(e){{}}}})();</script>"""
SKIN_PICKER = """<script>(function(){var r=document.documentElement,bs=document.querySelectorAll("[data-skin-pick]");
function sync(){var s=r.getAttribute("data-skin")||"klassisk";bs.forEach(function(b){b.setAttribute("aria-pressed",String(b.dataset.skinPick===s))})}
bs.forEach(function(b){b.addEventListener("click",function(){var s=b.dataset.skinPick;if(s==="klassisk")r.removeAttribute("data-skin");else r.setAttribute("data-skin",s);
try{localStorage.setItem("%s",s)}catch(e){}sync()})});sync()})();</script>""" % SKIN_KEY


def _skin_picker():
    buttons = "".join(
        f'<button type="button" data-skin-pick="{key}" aria-pressed="{str(key == "klassisk").lower()}">'
        f'<span class="sw" aria-hidden="true" style="background:conic-gradient({colors[0]} 0 120deg, {colors[1]} 0 240deg, {colors[2]} 0)"></span>{name}</button>'
        for key, (name, colors, _) in SKINS.items())
    return f'<div class="skins" role="group" aria-label="Tema">{buttons}</div>'


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

    if scorer:
        pens = f' <small>{p["penalties"]} str.</small>' if p["penalties"] else ""
        hero = [(p["goals"], "mål" + pens), (p["assists"], "målgivende")]
        hero.sort(key=lambda h: -h[0])  # the larger of the two leads; goals on a tie
        if p["goals"] and p.get("goalShare") is not None:
            hero.append((f'{round(100 * p["goalShare"])} %', "av lagets mål"))
    else:
        hero = [(p["starts"], f"av {played} kamper fra start" if played else "kamper fra start")]
    hero_html = "".join(f'<div class="{"lead" if i == 0 else ""}{" zero" if v == 0 else ""}"><b>{v}</b><span>{label}</span></div>'
                        for i, (v, label) in enumerate(hero))

    form = ""
    if scorer:
        last5 = p["last5Goals"] + p["last5Assists"]
        tone = " hot" if last5 >= HOT_LAST5 else " cold" if not last5 and p["goals"] + p["assists"] >= KEY_MIN_CONTRIBUTIONS else ""
        flag = "<em>i form</em>" if tone == " hot" else ""
        form = (f'<p class="p-form{tone}"><span>Siste 5</span>'
                f'<b>{p["last5Goals"]} mål, {p["last5Assists"]} målgivende</b>{flag}</p>')

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
            f'<div class="p-hero" aria-label="Tall fra {league}">{hero_html}</div>{form}'
            f'<div class="p-foot"><p>{" · ".join(fine)}</p><p>{rating}</p></div></div>')


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
<link rel="stylesheet" href="{FONTS}">
<style>{CSS}{SKIN_CSS}</style>
{SKIN_BOOT}
<div class="wrap">
  <header class="top">
    <span class="eyebrow">Tipping · {c["dayName"]} {_date_long(first)}</span>
    <h1>{title}</h1>
    <div class="meta"><span>Spillestopp <b>{_kick(c["saleStop"])}</b></span><span>Omsetning <b>{_nok(c["turnover"]["amount"])}</b></span><span><b>12</b> kamper</span></div>
    {_skin_picker()}
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
</div>
{SKIN_PICKER}"""
    site_dir.mkdir(parents=True, exist_ok=True)
    out = site_dir / f"{coupon_dir.name}.html"
    out.write_text(f'<!doctype html>\n<html lang="nb">\n<head>\n<meta charset="utf-8">\n'
                   f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n{body}\n</body>\n</html>\n')
    if fragment_path:
        Path(fragment_path).write_text(body)
    return out
