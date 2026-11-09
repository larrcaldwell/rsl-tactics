"""Generate DEMO data (synthetic, fictional teams) through the real pipeline code, into web/demo-data.
Used to test the app and to preview it offline. The app shows a DEMO banner when loading it (?demo=1).
Never writes to /data.
"""
import os, sys, random, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["RSL_DATA_DIR"] = os.path.join(os.path.dirname(HERE), "web", "demo-data")
sys.path.insert(0, HERE)
from common import *
import profiles, prematch, live, sources as S

random.seed(11)
RSL = "Real Salt Lake"
NAMES = [RSL, "Demo United"] + [f"Demo Club {i:02d}" for i in range(1, 29)]
TRAIT = {n: dict(poss=random.uniform(-6, 6), cross=random.uniform(-3, 3), long=random.uniform(-4, 4),
                 press=random.uniform(-3, 3), shots=random.uniform(-2, 2), leak=random.uniform(-2, 2)) for n in NAMES}
TRAIT[RSL].update(poss=5.5, cross=2.6, long=-3.0, press=1.5, shots=1.2, leak=0.4)
TRAIT["Demo United"].update(poss=-4.0, cross=-0.5, long=3.2, press=-2.6, shots=-0.8, leak=1.6)
TRAIT["Demo United"]["crossleak"] = 3.0


def team_game(a, b, poss):
    ta, tb = TRAIT[a], TRAIT[b]
    passes = max(180, 300 + poss * 4.2 + random.gauss(0, 25))
    long_rate = max(0.06, 0.15 + ta["long"] * 0.015 + random.gauss(0, 0.015))
    shots = max(3, 12 + ta["shots"] * 1.6 + (tb["leak"]) * 1.2 + (poss - 50) * 0.1 + random.gauss(0, 2.5))
    crosses = max(4, 17 + ta["cross"] * 2.2 + tb.get("crossleak", 0) * 1.6 + random.gauss(0, 3))
    tackles = max(8, 17 - ta["press"] * 1.1 - (poss - 50) * 0.12 + random.gauss(0, 2.5))
    sot = max(1, shots * random.uniform(0.28, 0.42))
    xg = max(0.2, shots * random.uniform(0.09, 0.12) + (tb["leak"] * 0.05))
    return {"possession_pct": round(poss, 1), "shots": round(shots), "shots_on_target": round(sot), "xg": None,
            "passes": round(passes), "pass_accuracy_pct": round(min(92, 72 + poss * 0.2 + random.gauss(0, 2)), 1),
            "long_balls": round(passes * long_rate), "crosses": round(crosses),
            "crosses_completed": round(crosses * random.uniform(0.2, 0.36)), "corners": round(max(0, 5 + ta["shots"] * 0.6 + random.gauss(0, 2))),
            "tackles": round(tackles), "interceptions": round(max(4, 9 + random.gauss(0, 2))), "fouls": round(max(5, 11 + random.gauss(0, 2.5))),
            "saves": 0, "blocked_shots": 3, "clearances": 20,
            "attack_side": dict(left_pct=None, center_pct=None, right_pct=None),
            "final_third_entries": None, "box_touches": None}


def fake_matches():
    out, mid = [], 1
    start = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)
    for rnd in range(20):
        order = NAMES[:]; random.shuffle(order)
        for i in range(0, len(order), 2):
            h, a = order[i], order[i + 1]
            ph = max(30, min(70, 50 + (TRAIT[h]["poss"] - TRAIT[a]["poss"]) * 1.3 + 2 + random.gauss(0, 4)))
            sh, sa = team_game(h, a, ph), team_game(a, h, 100 - ph)
            gh = max(0, round(sh["shots"] * 0.11 + random.gauss(0, 0.8))); ga = max(0, round(sa["shots"] * 0.11 + random.gauss(0, 0.8)))
            out.append({"id": f"d{mid}", "date": (start + dt.timedelta(days=rnd * 7, hours=i)).isoformat(), "home": h, "away": a,
                        "hs": gh, "as": ga, "stats": {"home": sh, "away": sa}}); mid += 1
    return out


def main():
    ms = fake_matches()
    teams = profiles.build(ms, {n: {"xg_pg": 1.0 + TRAIT[n]["shots"] * 0.12 + TRAIT[n]["poss"] * 0.02 + random.gauss(0, .05),
                                    "xg_ag_pg": 1.2 + TRAIT[n]["leak"] * 0.12 + random.gauss(0, .05), "games": 20} for n in NAMES})
    for n in (RSL, "Demo United"):
        teams[n]["attack_side"] = dict(left_pct=24, center_pct=31, right_pct=45) if n == RSL else dict(left_pct=41, center_pct=33, right_pct=26)
    prof = {"season": 2026, "generated_at": now_iso(), "matches_used": len(ms), "new_matches": 0,
            "source": "DEMO (synthetic)", "xg_available": True, "teams": teams}
    write_json(path("profiles.json"), prof)
    kick = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).replace(microsecond=0).isoformat()
    match = {"id": "demo1", "date": kick, "home": RSL, "away": "Demo United", "state": "pre"}
    write_json(path("schedule.json"), {"generated_at": now_iso(), "season": 2026, "matches": [match], "next": match, "last_completed": None})
    prematch_out = prematch.make_matchup(prof, match, "upcoming")
    prematch_out["demo"] = True
    write_json(path("matchup.json"), prematch_out)
    # halftime snapshot: RSL crossing a lot and not completing, Demo United leading on the counter
    ht = {"match_id": "demo1", "source": "fotmob", "source_role": "primary", "fetched_at": now_iso(), "status": "ht", "minute": 45, "period": None,
          "teams": {"home": {"name": RSL, "is_rsl": True, "score": 0}, "away": {"name": "Demo United", "is_rsl": False, "score": 1}},
          "stats": {"home": dict(team_game(RSL, "Demo United", 63), possession_pct=63, shots=9, shots_on_target=2, xg=0.62, crosses=13, crosses_completed=2, passes=290, tackles=6,
                                 attack_side=dict(left_pct=19, center_pct=26, right_pct=55), long_balls=22),
                    "away": dict(team_game("Demo United", RSL, 37), possession_pct=37, shots=4, shots_on_target=2, xg=0.9, crosses=3, crosses_completed=1, passes=170, tackles=11,
                                 attack_side=dict(left_pct=48, center_pct=30, right_pct=22), long_balls=30)},
          "shots": [], "events": []}
    h = live.make_halftime(ht, prof)
    h["demo"] = True
    write_json(path("halftime.json"), h)
    write_json(path("live.json"), {"match": match, "snapshot": ht, "chain": [{"source": "fotmob", "ok": True}], "updated_at": now_iso()})
    write_json(path("health.json"), {"sources": {"fotmob": {"ok": True, "detail": "demo"}, "espn": {"ok": True, "detail": "demo"},
                                                  "asa": {"ok": True, "detail": "demo"}, "api-football": {"ok": None, "detail": "no key"}},
                                     "events": [], "updated_at": now_iso()})
    print("demo data written to", DATA)
    print("RSL keys:", [c["title"] for c in prematch_out["matchup"]["keys"]])
    print("HT cards:", [c["title"] for c in h["cards"]])


if __name__ == "__main__":
    main()
