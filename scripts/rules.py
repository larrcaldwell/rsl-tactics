"""Rules engine. Each rule needs specific inputs, fires only when they exist and the condition
holds, and emits a card: Data (numbers), Meaning, Watch for, plus a Measured/Inference label,
the numbers used, and the rule text so the app can show exactly why it fired.

House style for all copy: direct, brief, no em dashes.
"""
from common import METRICS

RSL = "Real Salt Lake"


def short(name):
    return "RSL" if name == RSL else name


def M(prof, team, key):
    return (prof["teams"].get(team, {}).get("metrics", {}) or {}).get(key)


def fv(key, v):
    return f"{v:.{METRICS[key]['d']}f}"


def rk(m):
    return f"#{m['rank']} of {m['of']}"


def num_entry(team, key, m):
    return {"team": short(team), "key": key, "label": METRICS[key]["label"], "value": round(m["v"], 2),
            "rank": f"{m['rank']}/{m['of']}", "pct": m["pct"], "term": METRICS[key]["term"]}


def card(cid, scope, conf, title, data, meaning, watch, impact, numbers, rule):
    return {"id": cid, "scope": scope, "confidence": conf, "title": title, "data": data, "meaning": meaning,
            "watch": watch, "impact": round(float(impact), 3), "numbers": numbers, "rule": rule}


def have(*ms):
    return all(m is not None for m in ms)


# ------------------------------------------------------------------ style labels
def style_label(prof, team):
    po, lp, cr = M(prof, team, "poss"), M(prof, team, "long_pct"), M(prof, team, "crosses")
    if have(po, lp) and po["pct"] >= 70 and lp["pct"] <= 40:
        return "possession"
    if have(lp, po) and lp["pct"] >= 70 and po["pct"] <= 50:
        return "direct"
    if have(cr) and cr["pct"] >= 70:
        return "wide"
    return "balanced"


def press_label(prof, team):
    pp = M(prof, team, "ppda")
    if not pp:
        return None
    return "aggressive" if pp["pct"] <= 30 else "passive" if pp["pct"] >= 70 else "mid"


# ------------------------------------------------------------------ season synopsis cards
def season_cards(prof, team):
    t = short(team)
    out = []
    po, lp, cr, cp = (M(prof, team, k) for k in ("poss", "long_pct", "crosses", "cross_pct"))
    sl = style_label(prof, team)
    if sl == "possession":
        out.append(card("style_possession", "style", "Measured", f"{t} build through the middle with the ball",
            f"{fv('poss', po['v'])}% possession ({rk(po)}). Long balls are {fv('long_pct', lp['v'])}% of passes ({rk(lp)}, low = short passing).",
            "They keep the ball and build short. They want to dictate tempo and make the opponent chase.",
            "Goalkeeper and center backs passing short, patient circulation, fullbacks high. The opponent sitting in a mid or low block.",
            (po["pct"] + (100 - lp["pct"])) / 200, [num_entry(team, "poss", po), num_entry(team, "long_pct", lp)],
            "Possession pct >= 70 and long ball share pct <= 40 (percentile vs MLS)."))
    elif sl == "direct":
        out.append(card("style_direct", "style", "Measured", f"{t} play direct",
            f"Long balls are {fv('long_pct', lp['v'])}% of passes ({rk(lp)}). Possession {fv('poss', po['v'])}% ({rk(po)}).",
            "They skip the build-up. They are comfortable without the ball and look to win it and go forward fast.",
            "Goal kicks and center back passes going long, second-ball fights in midfield, quick forward runs after a turnover.",
            (lp["pct"] + (100 - po["pct"])) / 200, [num_entry(team, "long_pct", lp), num_entry(team, "poss", po)],
            "Long ball share pct >= 70 and possession pct <= 50."))
    elif sl == "wide":
        out.append(card("style_wide", "style", "Measured", f"{t} attack wide and cross",
            f"{fv('crosses', cr['v'])} crosses per game ({rk(cr)})" + (f", {fv('cross_pct', cp['v'])}% accurate ({rk(cp)})." if cp else "."),
            "They get the ball to the flanks and put it in the box rather than playing through the middle.",
            "Fullbacks and wingers delivering early crosses, a target forward attacking the near post, clearances turning into corners.",
            cr["pct"] / 100, [num_entry(team, "crosses", cr)] + ([num_entry(team, "cross_pct", cp)] if cp else []),
            "Crosses per game pct >= 70."))
    elif have(po):
        out.append(card("style_balanced", "style", "Measured", f"{t} have no extreme style",
            f"Possession {fv('poss', po['v'])}% ({rk(po)})" + (f", long balls {fv('long_pct', lp['v'])}% of passes ({rk(lp)})." if lp else "."),
            "They mix short and direct play and adapt to the game.",
            "Watch the first 15 minutes to see which approach they lean on, then see if it changes after a goal.",
            0.15, [num_entry(team, "poss", po)] + ([num_entry(team, "long_pct", lp)] if lp else []),
            "Fallback when no style rule fires."))
    pp = M(prof, team, "ppda")
    if pp:
        pl = press_label(prof, team)
        if pl == "aggressive":
            out.append(card("press_high", "press", "Inference", f"{t} press high",
                f"Approx PPDA {fv('ppda', pp['v'])} ({rk(pp)}, #1 = most passive). Opponents get few passes per defensive action.",
                "They squeeze the opponent early and try to win it high. This is a proxy built from tackles, interceptions and fouls, so treat it as likely, not certain.",
                "Forwards closing the goalkeeper and center backs, a compact line pushed up, fouls in the opponent's half.",
                (100 - pp["pct"]) / 100, [num_entry(team, "ppda", pp)], "PPDA percentile <= 30. PPDA here = opponent passes / (tackles + interceptions + fouls)."))
        elif pl == "passive":
            out.append(card("press_low", "press", "Inference", f"{t} sit off and let the opponent pass",
                f"Approx PPDA {fv('ppda', pp['v'])} ({rk(pp)}, #1 = most passive).",
                "They defend in a mid or low block and let the opponent have the ball in front of them. Proxy metric, so likely, not certain.",
                "Two compact banks of four, little pressure on the opponent's center backs, space between the lines for a midfielder to receive.",
                pp["pct"] / 100, [num_entry(team, "ppda", pp)], "PPDA percentile >= 70."))
    for key, cid, label, meaning, watch in (
        ("shots_ag", "vuln_shots", "concede a lot of shots", "Their structure lets opponents get shots away.", "Opponents shooting from the edge of the box, midfield not tracking runners."),
        ("crosses_ag", "vuln_crosses", "concede a lot of crosses", "Opponents reach the flanks easily, and the box gets tested in the air.", "Opposing fullbacks and wingers free to deliver, a long ball to the far post, set-piece pressure after blocked crosses."),
        ("corners_ag", "vuln_corners", "concede a lot of corners", "They are pushed back and clear the ball behind. Set pieces become a real chance source.", "Opponents winning corners in bunches, mark-up and second balls decide it.")):
        m = M(prof, team, key)
        if m and m["pct"] >= 75:
            out.append(card(cid, "vulnerability", "Measured", f"{t} {label}",
                f"{fv(key, m['v'])} {METRICS[key]['label'].lower()} per game ({rk(m)}, #1 = concedes the most).",
                meaning, watch, m["pct"] / 100 * 0.9, [num_entry(team, key, m)], f"{METRICS[key]['label']} percentile >= 75."))
    xa = M(prof, team, "xg_ag")
    if xa and xa["pct"] >= 75:
        out.append(card("vuln_xg", "vulnerability", "Measured", f"{t} concede high quality chances",
            f"{fv('xg_ag', xa['v'])} xG conceded per game ({rk(xa)}, #1 = most).",
            "Their opponents get good looks, not just shots. This is a defensive problem, not bad luck.",
            "Through balls and cutbacks reaching the box, goalkeeper facing one-on-ones.",
            xa["pct"] / 100, [num_entry(team, "xg_ag", xa)], "xG conceded percentile >= 75."))
    xg, go = M(prof, team, "xg"), M(prof, team, "goals")
    if have(xg, go) and abs(go["v"] - xg["v"]) >= 0.2:
        over = go["v"] > xg["v"]
        out.append(card("finishing", "finishing", "Measured", f"{t} are {'outscoring' if over else 'underperforming'} their chances",
            f"{fv('goals', go['v'])} goals vs {fv('xg', xg['v'])} xG per game.",
            "They are scoring more than their chances suggest, which tends to cool off." if over else "They create more than they score, so goals may come with the same play.",
            "Look at shot quality: long shots and low-angle finishes mean the numbers are flattering." if over else "Look for good chances wasted. The attack is working, the finishing is not.",
            min(abs(go["v"] - xg["v"]) / 0.6, 1) * 0.7, [num_entry(team, "goals", go), num_entry(team, "xg", xg)], "|goals - xG| per game >= 0.2."))
    f = prof["teams"][team]["form"]
    d = (f["last5"]["ppg"] or 0) - (f["season"]["ppg"] or 0)
    if abs(d) >= 0.6:
        out.append(card("form", "form", "Measured", f"{t} are {'in form' if d > 0 else 'out of form'}",
            f"Last 5: {f['last5']['ppg']:.1f} points per game ({''.join(f['last5']['results'])}) vs {f['season']['ppg']:.1f} on the season.",
            "Recent results are well " + ("above" if d > 0 else "below") + " their season level.",
            "Confidence and shape. Hot teams press and attack with energy early, cold teams tighten up and wait for mistakes.",
            min(abs(d) / 1.5, 1) * 0.6, [], "|last 5 ppg - season ppg| >= 0.6."))
    out.sort(key=lambda c: -c["impact"])
    return out


# ------------------------------------------------------------------ matchup (A's strengths vs B's weaknesses)
def pair(prof, a, b):
    ta, tb = short(a), short(b)
    out = []

    def add(cid, conf, title, data, meaning, watch, impact, nums, rule):
        out.append(card(cid, "key", conf, title, data, meaning, watch, impact, nums, rule))

    ca, cb = M(prof, a, "crosses"), M(prof, b, "crosses_ag")
    if have(ca, cb) and ca["pct"] >= 65 and cb["pct"] >= 60:
        add(f"k_wide_{ta}", "Measured", f"{ta} will cross, and {tb} allow it",
            f"{ta} average {fv('crosses', ca['v'])} crosses ({rk(ca)}). {tb} concede {fv('crosses_ag', cb['v'])} ({rk(cb)}, #1 = most).",
            f"{ta} lean on crosses and {tb} do little to stop them.",
            f"{ta} fullbacks and wingers getting to the byline, early deliveries, {tb} defenders clearing under pressure and giving up corners.",
            (ca["pct"] + cb["pct"]) / 200, [num_entry(a, "crosses", ca), num_entry(b, "crosses_ag", cb)],
            "A crosses pct >= 65 and B crosses conceded pct >= 60.")
    sa, sb = M(prof, a, "shots"), M(prof, b, "shots_ag")
    if have(sa, sb) and sa["pct"] >= 65 and sb["pct"] >= 60:
        add(f"k_shots_{ta}", "Measured", f"{ta} shoot a lot against a team that concedes shots",
            f"{ta} take {fv('shots', sa['v'])} shots ({rk(sa)}). {tb} concede {fv('shots_ag', sb['v'])} ({rk(sb)}, #1 = most).",
            f"Expect plenty of {ta} attempts. Volume is likely, quality is the question.",
            f"{ta} shooting from outside the box, {tb} goalkeeper busy, blocked shots and rebounds.",
            (sa["pct"] + sb["pct"]) / 200 * 0.95, [num_entry(a, "shots", sa), num_entry(b, "shots_ag", sb)],
            "A shots pct >= 65 and B shots conceded pct >= 60.")
    xa, xb = M(prof, a, "xg"), M(prof, b, "xg_ag")
    if have(xa, xb) and xa["pct"] >= 65 and xb["pct"] >= 60:
        add(f"k_xg_{ta}", "Measured", f"{ta} create quality against a leaky {tb} defense",
            f"{ta} generate {fv('xg', xa['v'])} xG per game ({rk(xa)}). {tb} concede {fv('xg_ag', xb['v'])} ({rk(xb)}, #1 = most).",
            f"{ta} get good chances and {tb} give them up.",
            f"{ta} through balls and cutbacks, {tb} back line dropping or getting split.",
            (xa["pct"] + xb["pct"]) / 200, [num_entry(a, "xg", xa), num_entry(b, "xg_ag", xb)], "A xG pct >= 65 and B xG conceded pct >= 60.")
    pa, pb = M(prof, a, "poss"), M(prof, b, "ppda")
    if have(pa, pb) and pa["pct"] >= 65 and pb["pct"] >= 60:
        add(f"k_poss_{ta}", "Inference", f"{ta} should own the ball, {tb} will let them",
            f"{ta} hold {fv('poss', pa['v'])}% possession ({rk(pa)}). {tb} approx PPDA {fv('ppda', pb['v'])} ({rk(pb)}, #1 = most passive).",
            f"{tb} sit off and {ta} like the ball. Expect long spells of {ta} possession, and the question is whether they break the block.",
            f"{ta} circulating across the back line, {tb} in two banks, {ta} wide players taking the ball in space and trying to isolate.",
            (pa["pct"] + pb["pct"]) / 200 * 0.9, [num_entry(a, "poss", pa), num_entry(b, "ppda", pb)],
            "A possession pct >= 65 and B PPDA pct >= 60 (passive).")
    pa2, pb2, lb = M(prof, a, "ppda"), M(prof, b, "poss"), M(prof, b, "long_pct")
    if have(pa2, pb2, lb) and pa2["pct"] <= 35 and pb2["pct"] >= 60 and lb["pct"] <= 40:
        add(f"k_press_{ta}", "Inference", f"{ta}'s press meets {tb}'s short build-up",
            f"{ta} approx PPDA {fv('ppda', pa2['v'])} ({rk(pa2)}). {tb} possession {fv('poss', pb2['v'])}%, long balls {fv('long_pct', lb['v'])}% ({rk(lb)}).",
            f"{tb} want to play out from the back and {ta} want to win it high. Whoever wins that fight sets the game.",
            f"{ta} forwards jumping on {tb} goalkeeper and center backs, {tb} either splitting the press with a quick pass or bailing out long.",
            (1 - pa2["pct"] / 100 + pb2["pct"] / 100) / 2 * 0.95, [num_entry(a, "ppda", pa2), num_entry(b, "poss", pb2), num_entry(b, "long_pct", lb)],
            "A PPDA pct <= 35 (aggressive), B possession pct >= 60 and B long ball share pct <= 40.")
    la, pb3 = M(prof, a, "long_pct"), M(prof, b, "ppda")
    if have(la, pb3) and la["pct"] >= 65 and pb3["pct"] <= 35:
        add(f"k_bypass_{ta}", "Inference", f"{ta} can go over {tb}'s press",
            f"{ta} long balls {fv('long_pct', la['v'])}% of passes ({rk(la)}). {tb} approx PPDA {fv('ppda', pb3['v'])} ({rk(pb3)}).",
            f"{tb} press high and {ta} will skip it. Space opens behind the {tb} midfield if the first ball is won.",
            f"{ta} goalkeeper going long, a forward winning the header and a runner dropping onto the second ball, {tb} line stretched.",
            (la["pct"] + (100 - pb3["pct"])) / 200 * 0.9, [num_entry(a, "long_pct", la), num_entry(b, "ppda", pb3)],
            "A long ball share pct >= 65 and B PPDA pct <= 35.")
    ka, kb = M(prof, a, "corners"), M(prof, b, "corners_ag")
    if have(ka, kb) and ka["pct"] >= 70 and kb["pct"] >= 60:
        add(f"k_setp_{ta}", "Measured", f"{ta} win corners and {tb} give them away",
            f"{ta} {fv('corners', ka['v'])} corners per game ({rk(ka)}). {tb} concede {fv('corners_ag', kb['v'])} ({rk(kb)}, #1 = most).",
            "Set pieces will matter in this game.",
            f"{ta} corners and wide free kicks into a crowded box, {tb} marking tight and clearing short.",
            (ka["pct"] + kb["pct"]) / 200 * 0.8, [num_entry(a, "corners", ka), num_entry(b, "corners_ag", kb)],
            "A corners pct >= 70 and B corners conceded pct >= 60.")
    cv, sob = M(prof, a, "conv"), M(prof, b, "sot_ag")
    if have(cv, sob) and cv["pct"] >= 70 and sob["pct"] >= 60:
        add(f"k_fin_{ta}", "Measured", f"{ta} finish well and {tb} allow shots on target",
            f"{ta} convert {fv('conv', cv['v'])}% of shots ({rk(cv)}). {tb} concede {fv('sot_ag', sob['v'])} shots on target ({rk(sob)}).",
            f"{ta} do not need many chances and {tb} give up accurate ones.",
            f"Goals from few attempts, {tb} goalkeeper tested early.",
            (cv["pct"] + sob["pct"]) / 200 * 0.85, [num_entry(a, "conv", cv), num_entry(b, "sot_ag", sob)],
            "A conversion pct >= 70 and B shots on target conceded pct >= 60.")
    return out


def matchup(prof, rsl, opp, venue_note=""):
    cards = pair(prof, rsl, opp) + pair(prof, opp, rsl)
    cards.sort(key=lambda c: -c["impact"])
    keys = cards[:5]
    for c in keys:
        c["scope"] = "key"
    # Likely game script
    sr, so = style_label(prof, rsl), style_label(prof, opp)
    pr, po = M(prof, rsl, "poss"), M(prof, opp, "poss")
    script = ""
    if have(pr, po):
        exp = (pr["v"] + (100 - po["v"])) / 2
        lead = "RSL" if exp >= 52 else short(opp) if exp <= 48 else None
        script = (f"RSL average {pr['v']:.0f}% possession and {short(opp)} average {po['v']:.0f}%, so expect RSL to see roughly {exp:.0f}% of the ball. "
                  + (f"{lead} should have more of it." if lead else "Expect an even split of possession."))
        labels = {"possession": "a possession side", "direct": "a direct side", "wide": "a crossing side", "balanced": "a balanced side"}
        script += f" RSL look like {labels[sr]}, {short(opp)} like {labels[so]}."
        if sr == "possession" and press_label(prof, opp) == "passive":
            script += f" {short(opp)} will likely sit off, so the fight is whether RSL can break a compact block."
        elif so == "direct" and sr != "direct":
            script += f" {short(opp)} will try to go over the top of RSL, so watch the space behind the RSL line after turnovers."
        if keys:
            script += f" The main battle: {keys[0]['title']}."
    return {"keys": keys, "script": script, "all_candidates": len(cards)}


# ------------------------------------------------------------------ halftime
COUNT = ["shots", "sot", "crosses", "passes", "tackles", "interceptions", "fouls", "corners", "xg"]
PLAN_ROWS = ["poss", "shots", "sot", "crosses", "passes", "pass_pct", "tackles", "xg"]


def ht_row(st):
    g = lambda k: st.get(k) if isinstance(st.get(k), (int, float)) else None
    r = {"poss": g("possession_pct"), "shots": g("shots"), "sot": g("shots_on_target"), "crosses": g("crosses"),
         "passes": g("passes"), "pass_pct": g("pass_accuracy_pct"), "tackles": g("tackles"),
         "interceptions": g("interceptions"), "fouls": g("fouls"), "corners": g("corners"), "xg": g("xg")}
    if r["crosses"] and g("crosses_completed") is not None:
        r["cross_pct"] = 100.0 * st["crosses_completed"] / r["crosses"]
    if r["passes"] and g("long_balls") is not None:
        r["long_pct"] = 100.0 * st["long_balls"] / r["passes"]
    return r


def half_norm(prof, team, key):
    m = M(prof, team, key)
    if not m:
        return None
    return m["v"] / 2 if key in COUNT else m["v"]


DEV_TEXT = {
    ("poss", 1): ("holding far more of the ball than normal", "Game state or an opponent sitting deeper. Check whether it is producing shots.", "Longer spells in the opponent half, opponent falling back into a block."),
    ("poss", -1): ("ceding the ball more than normal", "They are being pressed or choosing to sit and counter.", "Clearances, long goal kicks, a deeper line, quick forward runs after winning it."),
    ("shots", 1): ("shooting more than normal", "They are getting into shooting positions more often.", "More box entries, the opponent blocking and clearing more."),
    ("shots", -1): ("shooting less than normal", "The opponent is limiting their access to the box.", "Passes stalling at the edge of the box, shots from distance."),
    ("crosses", 1): ("crossing more than normal", "The middle is blocked, or they are targeting the wings on purpose.", "Wide players isolated, a high ball into the box every few possessions."),
    ("crosses", -1): ("crossing less than normal", "They are not reaching the byline.", "Play through the middle, fullbacks held back."),
    ("tackles", 1): ("making more tackles than normal", "They are defending more, either pinned back or pressing harder.", "Duels in midfield, more fouls, a team trying to win it early."),
    ("passes", 1): ("passing more than normal", "More time on the ball, usually because the opponent sat deeper.", "Slow circulation across the back, the opponent waiting."),
    ("passes", -1): ("passing less than normal", "The game is stretched, more direct, or they are under pressure.", "Long balls, quick transitions, fewer long possessions."),
}


def halftime(snap, prof, rsl_side):
    """snap = normalized match at halftime. Returns plan-vs-reality table and cards."""
    sides = {"home": snap["teams"]["home"]["name"], "away": snap["teams"]["away"]["name"]}
    score = {"home": snap["teams"]["home"].get("score", 0), "away": snap["teams"]["away"].get("score", 0)}
    rows = {s: ht_row(snap["stats"][s]) for s in sides}
    table, cards = [], []
    for s, team in sides.items():
        for k in PLAN_ROWS:
            act, norm = rows[s].get(k), half_norm(prof, team, k)
            if act is None or norm is None:
                continue
            dev = None if norm == 0 else (act - norm) / norm * 100
            table.append({"team": short(team), "side": s, "key": k, "label": METRICS[k]["label"] + (" (per half)" if k in COUNT else ""),
                          "norm": round(norm, 1), "actual": round(act, 1), "dev_pct": None if dev is None else round(dev)})
    # deviations
    for s, team in sides.items():
        t = short(team)
        for k in ("poss", "shots", "crosses", "tackles", "passes"):
            act, norm = rows[s].get(k), half_norm(prof, team, k)
            if act is None or norm is None or norm == 0:
                continue
            if k == "poss":
                big = abs(act - norm) >= 8; mag = abs(act - norm) / 20
            else:
                big = norm >= 2 and abs(act - norm) / norm >= 0.15 and abs(act - norm) >= 2; mag = abs(act - norm) / norm
            dr = 1 if act > norm else -1
            txt = DEV_TEXT.get((k, dr))
            if big and txt:
                cards.append(card(f"ht_dev_{k}_{s}", "deviation", "Measured", f"{t} are {txt[0]}",
                    f"{t} first half {METRICS[k]['label'].lower()}: {act:.0f} vs season norm {norm:.0f} per half" + (" (points)." if k == "poss" else "."),
                    txt[1], txt[2], min(mag, 1.5) * 0.8, [{"team": t, "key": k, "label": METRICS[k]["label"], "value": round(act, 1), "rank": "norm " + f"{norm:.1f}", "pct": None, "term": METRICS[k]["term"]}],
                    "First half value differs from the season half-norm by 15% or more (8 points for possession)."))
    # effectiveness
    for s, team in sides.items():
        t, r = short(team), rows[s]
        if (r.get("crosses") or 0) >= 5 and r.get("cross_pct") is not None and r["cross_pct"] < 25:
            cards.append(card(f"ht_cross_bad_{s}", "effectiveness", "Measured", f"{t} crossing is not working",
                f"{r['crosses']:.0f} crosses, {r['cross_pct']:.0f}% completed.",
                "High volume, low return. The delivery is poor or the defense is winning the ball in the air.",
                "Expect a change: cutbacks, play through the middle, or a target forward off the bench.", 0.9 if r["crosses"] >= 8 else 0.7,
                [{"team": t, "key": "crosses", "label": "Crosses", "value": r["crosses"], "rank": "", "pct": None, "term": "crosses"}],
                "Crosses >= 5 and completion < 25% in the first half."))
        if (r.get("shots") or 0) >= 6 and r.get("sot") is not None and r["sot"] / r["shots"] < 0.25:
            cards.append(card(f"ht_shots_bad_{s}", "effectiveness", "Measured", f"{t} shots are not testing the keeper",
                f"{r['shots']:.0f} shots, {r['sot']:.0f} on target.",
                "Volume without threat. Likely long shots or blocked attempts.",
                "More patience in the final third, or a change of player to create better shots.", 0.75,
                [{"team": t, "key": "shots", "label": "Shots", "value": r["shots"], "rank": "", "pct": None, "term": "shots"}],
                "Shots >= 6 and shots on target share < 25%."))
        if r.get("xg") is not None and (r.get("shots") or 99) <= 5 and r["xg"] >= 0.8:
            cards.append(card(f"ht_xg_good_{s}", "effectiveness", "Measured", f"{t} are creating real chances with few shots",
                f"{r['xg']:.2f} xG on {r['shots']:.0f} shots.",
                "What they are doing works. Expect more of it.",
                "The same pattern of attack repeating, the opponent forced to change shape.", 0.85,
                [{"team": t, "key": "xg", "label": "xG", "value": r["xg"], "rank": "", "pct": None, "term": "xg"}],
                "xG >= 0.8 on 5 or fewer shots."))
        if (r.get("poss") or 0) >= 60 and (r.get("shots") or 99) <= 3:
            cards.append(card(f"ht_sterile_{s}", "effectiveness", "Measured", f"{t} have the ball but no shots",
                f"{r['poss']:.0f}% possession, {r['shots']:.0f} shots.",
                "Possession without penetration. The opponent is happy to let them pass in front of the block.",
                "A runner or dribbler off the bench, quicker switches, more crosses or shots from range.", 0.8,
                [{"team": t, "key": "poss", "label": "Possession %", "value": r["poss"], "rank": "", "pct": None, "term": "possession"}],
                "Possession >= 60% and 3 or fewer shots."))
    # game state and adjustments (inferences)
    hs, as_ = score["home"], score["away"]
    for s, team in sides.items():
        o = "away" if s == "home" else "home"
        t, r, ro = short(team), rows[s], rows[o]
        diff = score[s] - score[o]
        if diff < 0:
            cards.append(card(f"ht_trail_{s}", "adjustment", "Inference", f"{t} are trailing and will push",
                f"Score {score[s]}-{score[o]} at halftime. Shots {r.get('shots') or 0:.0f} to {ro.get('shots') or 0:.0f}.",
                "Teams that are behind commit more players forward and take more risk.",
                f"{t} fullbacks higher, an extra attacker on, more crosses. That also leaves space behind them for a counter.", 0.9,
                [], "Team is behind at halftime."))
            if (r.get("crosses") or 0) >= 6:
                cards.append(card(f"ht_target_{s}", "adjustment", "Inference", f"{t} may bring on a target forward",
                    f"{r['crosses']:.0f} first-half crosses while trailing.",
                    "A team crossing this much and behind often adds a tall striker to use the deliveries.",
                    "A substitution around minute 55 to 65 for a big forward, crosses aimed at the penalty spot.", 0.7, [], "Trailing and crosses >= 6."))
        elif diff > 0:
            cards.append(card(f"ht_lead_{s}", "adjustment", "Inference", f"{t} are ahead and may sit deeper",
                f"Score {score[s]}-{score[o]} at halftime. Possession {r.get('poss') or 0:.0f}%.",
                "Teams that are ahead protect the lead and let the opponent have the ball.",
                f"A lower {t} line, fewer players forward, counters when they win it. Possession tends to shift toward the opponent.", 0.75,
                [], "Team is ahead at halftime."))
        if (ro.get("shots") or 0) >= 8 and diff >= 0:
            cards.append(card(f"ht_protect_{s}", "adjustment", "Inference", f"{t} are under pressure and may add a defender",
                f"Opponent shots {ro['shots']:.0f} in the first half.",
                "A team being outshot like this often changes shape to protect the box.",
                f"A back five or an extra holding midfielder for {t}, a winger dropping in to track the fullback.", 0.7, [], "Opponent shots >= 8 and team is not behind."))
    if hs == as_:
        cards.append(card("ht_level", "adjustment", "Inference", "Level at halftime, the next goal decides the shape",
            f"Score {hs}-{as_}.", "Neither team has to chase. The first goal of the second half forces the other to change.",
            "Both benches ready, substitutions around minute 60.", 0.5, [], "Score level at halftime."))
    cards.sort(key=lambda c: -c["impact"])
    working = [c for c in cards if c["scope"] == "effectiveness" and ("xg_good" in c["id"])]
    notworking = [c for c in cards if c["scope"] == "effectiveness" and ("xg_good" not in c["id"])]
    return {"table": table, "cards": cards[:10], "working": working, "not_working": notworking,
            "score": {"home": hs, "away": as_}, "teams": {s: short(n) for s, n in sides.items()}, "rsl_side": rsl_side}
