"""Season profiles: aggregate every completed MLS match (ESPN box scores, cached) into
per-team per-game averages with league rank and percentile. ASA xG is overlaid when reachable.
Usage: python scripts/profiles.py
"""
import time, statistics
from common import *
import sources as S


def update_match_cache(events, limit=600, pause=0.25):
    os.makedirs(os.path.join(CACHE, "matches"), exist_ok=True)
    new = 0
    for e in events:
        if e["state"] != "post":
            continue
        p = os.path.join(CACHE, "matches", f"{e['id']}.json")
        if os.path.exists(p):
            continue
        if new >= limit:
            break
        try:
            m = S.espn_summary(e["id"])
            has = any(v is not None for v in m["stats"]["home"].values())
            if not has:
                continue
            write_json(p, {"id": e["id"], "date": e["date"], "stage": e.get("stage", "regular"), "home": m["teams"]["home"]["name"],
                           "away": m["teams"]["away"]["name"], "hs": m["teams"]["home"]["score"],
                           "as": m["teams"]["away"]["score"], "stats": m["stats"]})
            new += 1
            time.sleep(pause)
        except Exception as ex:
            log_health("espn", False, f"summary {e['id']}: {ex}")
    return new


def load_matches():
    d = os.path.join(CACHE, "matches")
    if not os.path.isdir(d):
        return []
    return sorted((read_json(os.path.join(d, f)) for f in os.listdir(d) if f.endswith(".json")),
                  key=lambda m: m["date"] or "")


def _g(d, k):
    v = d.get(k)
    return v if isinstance(v, (int, float)) else None


def game_row(own, opp, gf, ga):
    """Derive one game's metric row for a team from its stats and the opponent's."""
    r = {"poss": _g(own, "possession_pct"), "passes": _g(own, "passes"), "pass_pct": _g(own, "pass_accuracy_pct"),
         "shots": _g(own, "shots"), "sot": _g(own, "shots_on_target"), "crosses": _g(own, "crosses"),
         "corners": _g(own, "corners"), "tackles": _g(own, "tackles"), "interceptions": _g(own, "interceptions"),
         "fouls": _g(own, "fouls"), "goals": gf, "xg": _g(own, "xg"),
         "shots_ag": _g(opp, "shots"), "sot_ag": _g(opp, "shots_on_target"), "crosses_ag": _g(opp, "crosses"),
         "corners_ag": _g(opp, "corners"), "goals_ag": ga, "xg_ag": _g(opp, "xg")}
    if r["passes"] and _g(own, "long_balls") is not None:
        r["long_pct"] = 100.0 * own["long_balls"] / r["passes"]
    if r["crosses"] and _g(own, "crosses_completed") is not None:
        r["cross_pct"] = 100.0 * own["crosses_completed"] / r["crosses"]
    da = sum(x for x in (r["tackles"], r["interceptions"], r["fouls"]) if x is not None)
    if _g(opp, "passes") and da:
        r["ppda"] = opp["passes"] / da
    if r["shots"]:
        r["conv"] = 100.0 * gf / r["shots"]
    return r


def mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def build(matches, asa=None):
    games = {}
    for m in matches:
        for side, opp_side in (("home", "away"), ("away", "home")):
            team = m[side]
            gf, ga = (m["hs"], m["as"]) if side == "home" else (m["as"], m["hs"])
            row = game_row(m["stats"][side], m["stats"][opp_side], gf, ga)
            pts = 3 if gf > ga else 1 if gf == ga else 0
            games.setdefault(team, []).append({"playoff": m.get("stage") == "playoff", "row": row, "pts": pts, "gf": gf, "ga": ga, "date": m["date"],
                                               "opp": m[opp_side], "venue": side})
    teams = {}
    for t, all_gl in games.items():
        gl = [g for g in all_gl if not g["playoff"]] or all_gl   # season norms exclude playoff games
        met = {k: mean([g["row"].get(k) for g in gl]) for k in METRICS}
        if asa and t in asa:  # ASA xG is the better source, override box-score xG
            met["xg"], met["xg_ag"] = asa[t]["xg_pg"], asa[t]["xg_ag_pg"]
        last5 = all_gl[-5:]   # form includes playoff results
        teams[t] = {"games": len(gl), "metrics": {k: {"v": v} for k, v in met.items() if v is not None},
                    "form": {"season": {"ppg": mean([g["pts"] for g in gl]), "gf": mean([g["gf"] for g in gl]),
                                        "ga": mean([g["ga"] for g in gl]),
                                        "shot_diff": mean([(g["row"].get("shots") or 0) - (g["row"].get("shots_ag") or 0) for g in gl])},
                             "last5": {"ppg": mean([g["pts"] for g in last5]), "gf": mean([g["gf"] for g in last5]),
                                       "ga": mean([g["ga"] for g in last5]),
                                       "shot_diff": mean([(g["row"].get("shots") or 0) - (g["row"].get("shots_ag") or 0) for g in last5]),
                                       "results": ["W" if g["pts"] == 3 else "D" if g["pts"] == 1 else "L" for g in last5]}},
                    "playoff_games": sum(1 for g in all_gl if g["playoff"]),
                    "recent": [{"date": g["date"][:10], "opp": g["opp"], "score": f'{g["gf"]}-{g["ga"]}', "venue": g["venue"], "playoff": g["playoff"]} for g in last5]}
    for k in METRICS:
        vals = sorted([(tm["metrics"][k]["v"], n) for n, tm in teams.items() if k in tm["metrics"]], reverse=True)
        N = len(vals)
        for i, (v, n) in enumerate(vals):
            teams[n]["metrics"][k].update({"rank": i + 1, "of": N, "pct": round(100.0 * (N - 1 - i) / max(N - 1, 1), 0)})
    return teams


def run():
    events = S.espn_season_events()
    if not events:
        raise RuntimeError("ESPN returned no events; keeping previous profiles")
    log_health("espn", True, f"{len(events)} events")
    new = update_match_cache(events)
    matches = load_matches()
    asa = None
    try:
        asa = S.asa_team_xg()
        log_health("asa", True, f"{len(asa)} teams")
    except Exception as ex:
        log_health("asa", False, ex)
    teams = build(matches, asa)
    prof = {"season": SEASON, "generated_at": now_iso(), "matches_used": len(matches), "new_matches": new,
            "source": "espn+asa" if asa else "espn (ASA unavailable, xG hidden)", "xg_available": bool(asa),
            "teams": teams}
    write_json(path("profiles.json"), prof)
    print(f"profiles: {len(teams)} teams, {len(matches)} matches, xG={'yes' if asa else 'no'}")
    return prof


if __name__ == "__main__":
    run()
