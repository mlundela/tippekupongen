# Language for `analysis.json`

The voice is a Norwegian tipping columnist who also reads xG: the register of Nettavisen's coupon previews (nettavisen.no/norsk-tipping), with our own split between quality and luck. Medium slang: the everyday sports desk, in full, grammatical sentences.

## Headline

The team is the subject, the verb is active, and the line says something about the match: «Formsterke Rosenborg møter et HamKam i fritt fall», «Folket har gått all-in på Stoke». Up to about nine words. The headline is about the football; the public and the odds belong in `crowd`.

## `take`

1. **Football first.** Open with the team's last match (`lastMatch`) or its form, then the opponent. Pick the one or two results that say something about the team.
2. **What the table hides.** The second paragraph separates quality from luck in plain words (see the table below), then the stakes, and ends with the **vurdering**: one short sentence with our verbal lean, such as «Rosenborg skal likevel være favoritter i Hamar» or «Dette er en vrien kamp». The vurdering names teams and outcomes in words. Signs (H/U/B), «sikker», guards and our own percentages belong to the rendered coupon. Keep the vurdering consistent with `render.system()`; where the coupon carries a bomb against our lean, say what makes the outsider worth it.

Percentages from the odds and the public live in `crowd` and `_coupon.intro`.

## Toolbox

- **Prefix adjective** for the team's profile: *formsterke, hjemmesterke, bortesvake, ubeseirede, nedrykkstruede, kontringssterke*.
- **A verdict on every record**: «knallsterke 10-0-1 hjemme», «middels 4-1-6 borte», «labre 0-1-4 borte», «stygge tall». Records are written V-U-T.
- **Stakes** from `table`: place, points, gap to the leader.
- **Nicknames** after the full name, once per team: *trønderne, kamma, Glimt, Knutsens mannskap, londonklubben*.
- **Idioms**, about one per paragraph: *smalt til med, slo kraftig tilbake, gikk på en smell, i fritt fall, holdt nullen, full pott, mellom slagene, vrien kamp, U-fare, kan ikke utelates*.

## Stats in plain words

xG is how much a team's chances are worth. The page says what it shows, in two forms, and the terms xG and PDO stay off the page, in `take` and in `stat` labels alike:

- **Between the teams, as a ratio.** Match xG, and season `xg` against `xgAgainst`, become how much more one side created: «Glimt skapte fem ganger så mye», «Bayern skapte halvparten mer», «lagene skapte omtrent like mye». The absolute values stay out.
- **Goals against chances, as effektivitet.** `xg` against goals scored, and `xgAgainst` against goals conceded, become how effective the team (or its opponents) has been, as a ratio: «nesten dobbelt så mange mål som sjansene tilsier», «bare to tredjedeler av det sjansene tilsier».

| `facts.json` | In the text |
|---|---|
| match `xg` | «Sarpsborg ble utspilt: Rosenborg skapte over tre ganger så mye», «skapte nesten dobbelt så mye, men tapte» |
| season `xg` vs `xgAgainst` | «skaper nesten tre ganger så mye som motstanderne», «skaper omtrent like mye som de slipper til» |
| goals vs `xg`, high | «kupongens mest effektive lag: nesten dobbelt så mange mål som sjansene tilsier» |
| goals vs `xg`, low | «ineffektive: bare to tredjedeler av det sjansene tilsier» |
| conceded vs `xgAgainst`, high | «motstanderne har vært effektive mot HamKam: 30 % flere mål enn sjansene tilsier» |
| high `conversion` | «43 % av skuddene på mål går inn, mot normalt rundt en tredjedel» |
| high `savePct` | «keeperen holder dem oppe: redder 75 %» |
| `pdo` far from 1,00 | «flyt i begge ender» (high) or «uflaks i begge ender» (low), backed by conversion and save % |

## `signal` and `noise`

`stat` is a short label, a number with a verdict word where it fits: «Knallsterke hjemme: 10-0-1». `text` says in one or two sentences why the number matters for this match.

## `crowd`

One or two sentences. Lead with how the public differs from the odds, with the percentages.
