"""Build data/matchup.json for the next RSL match (or the most recent one in replay mode).
Usage: python scripts/prematch.py [--auto] [--match-id ID] [--replay]
--auto only runs inside ~6h and ~1h before kickoff windows (for the hourly workflow).
"""
import sys, argparse, datetime as dt
from common import *
import rules, schedule as SC
import sources as S

COMPARE = ["poss", "passes", "long_pct", "shots", "sot", "xg", "crosses", "cross_pct", "corners",
           "ppda", "shots_ag", "xg_ag", "crosses_ag", "goals", "goals_ag"]


def team_block(prof, team):
    t = prof["teams"][team]
    return {"name": rules.short(team), "profile_key": team, "games": t["games"], "form": t["form"], "recent": t["recent"],
            "cards": rules.season_cards(prof, team), "style": rules.style_label(prof, team),
            "press": rules.press_label(prof, team), "attack_side": t.get("attack_side")}


def make_matchup(prof, match, mode):
    home, away = match["home"], match["away"]
    rsl = RSL_NAME if S.same_team(home, RSL_NAME) else away
    opp = away if rsl == home else home
    # map ESPN names onto profile names
    names = list(prof["teams"].keys())
    pick = lambda n: next((x for x in names if S.same_team(x, n)), None)
    rsl_p, opp_p = pick(rsl), pick(opp)
    if not rsl_p or not opp_p:
        raise LookupError(f"Team not in profiles: {rsl} / {opp}")
    cmp_rows = []
    for k in COMPARE:
        a, b = rules.M(prof, rsl_p, k), rules.M(prof, opp_p, k)
        if a and b:
            cmp_rows.append({"key": k, "label": METRICS[k]["label"], "term": METRICS[k]["term"],
                             "rsl": round(a["v"], 2), "opp": round(b["v"], 2),
                             "rsl_rank": f"{a['rank']}/{a['of']}", "opp_rank": f"{b['rank']}/{b['of']}"})
    mu = rules.matchup(prof, rsl_p, opp_p)
    playoff = match.get("stage") == "playoff"
    if playoff:
        mu["script"] += (" This is a playoff match. Season numbers are regular season, and knockout games usually play tighter and cagier, "
                         "with the team that scores first protecting the lead. Extra time and penalties are possible.")
    return {"generated_at": now_iso(), "mode": mode, "profiles_generated_at": prof["generated_at"],
            "profile_source": prof["source"], "xg_available": prof.get("xg_available", False),
            "match": {"id": match["id"], "date": match["date"], "home": home, "away": away,
                      "rsl_is_home": rsl == home, "opponent": opp, "stage": match.get("stage", "regular")},
            "rsl": team_block(prof, rsl_p), "opp": team_block(prof, opp_p), "compare": cmp_rows, "matchup": mu}


def run(match_id=None, auto=False, replay=False):
    sched = read_json(path("schedule.json"))
    prof = read_json(path("profiles.json"))
    if not sched or not prof:
        raise SystemExit("Need data/schedule.json and data/profiles.json first (run schedule.py and profiles.py).")
    now = dt.datetime.now(dt.timezone.utc)
    match, mode = None, "upcoming"
    if match_id:
        match = next((m for m in sched["matches"] if m["id"] == str(match_id)), None)
        mode = "replay" if match and match["state"] == "post" else "upcoming"
    elif replay or not sched.get("next"):
        match, mode = sched.get("last_completed"), "replay"
    else:
        match = sched["next"]
    if not match:
        raise SystemExit("No match found.")
    if auto and mode == "upcoming":
        mins = (SC.parse(match["date"]) - now).total_seconds() / 60
        if not (330 <= mins <= 400 or 50 <= mins <= 110):
            print(f"auto: {mins:.0f} min to kickoff, outside windows, skipping")
            return None
    out = make_matchup(prof, match, mode)
    write_json(path("matchup.json"), out)
    print(f"matchup written: {match['home']} v {match['away']} ({mode}), {len(out['matchup']['keys'])} keys")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true"); ap.add_argument("--replay", action="store_true")
    ap.add_argument("--match-id")
    a = ap.parse_args()
    run(a.match_id, a.auto, a.replay)
