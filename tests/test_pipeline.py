"""Offline tests. Run: python tests/test_pipeline.py
Covers: ESPN parser on a box-score-shaped fixture, fallback chain, halftime freeze, null-safe rules.
These use mocked sources because the real feeds need network. The verify-sources workflow
checks the real endpoints on GitHub Actions.
"""
import os, sys, json, shutil, tempfile, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = tempfile.mkdtemp()
os.environ["RSL_DATA_DIR"] = TMP
sys.path.insert(0, os.path.join(ROOT, "scripts"))
shutil.copy(os.path.join(ROOT, "web", "demo-data", "profiles.json"), os.path.join(TMP, "profiles.json"))
import common, sources as S, live, rules, profiles

ok = fail = 0
def check(name, cond):
    global ok, fail
    print(("PASS " if cond else "FAIL ") + name); ok += cond; fail += (not cond)

def stat(name, val): return {"name": name, "displayValue": str(val)}
ESPN_FIX = {"header": {"competitions": [{"id": "1", "date": "2026-11-01T01:00Z", "status": {"displayClock": "45'", "type": {"name": "STATUS_HALFTIME"}},
    "competitors": [{"homeAway": "home", "score": "0", "team": {"id": "10", "displayName": "Real Salt Lake"}}, {"homeAway": "away", "score": "1", "team": {"id": "11", "displayName": "Demo United"}}]}]},
  "boxscore": {"teams": [
    {"team": {"id": "10"}, "homeAway": "home", "statistics": [stat("possessionPct", 63), stat("totalShots", 9), stat("shotsOnTarget", 2), stat("totalPasses", 290), stat("passPct", 0.84), stat("totalCrosses", 13), stat("accurateCrosses", 2), stat("totalLongBalls", 22), stat("wonCorners", 5), stat("totalTackles", 6), stat("foulsCommitted", 5)]},
    {"team": {"id": "11"}, "homeAway": "away", "statistics": [stat("possessionPct", 37), stat("totalShots", 4), stat("shotsOnTarget", 2), stat("totalPasses", 170), stat("passPct", 0.78), stat("totalCrosses", 3), stat("accurateCrosses", 1), stat("totalLongBalls", 30), stat("wonCorners", 1), stat("totalTackles", 11), stat("foulsCommitted", 8)]}]},
  "keyEvents": [{"type": {"text": "Goal"}, "clock": {"displayValue": "31'"}, "team": {"displayName": "Demo United"}, "participants": [{"athlete": {"displayName": "Test Player"}}]}]}

snap = S.espn_parse_summary(ESPN_FIX, "1")
check("espn parser: status ht", snap["status"] == "ht")
check("espn parser: score and rsl flag", snap["teams"]["home"]["is_rsl"] and snap["teams"]["away"]["score"] == 1)
check("espn parser: pass pct scaled to 84", abs(snap["stats"]["home"]["pass_accuracy_pct"] - 84) < 0.01)
check("espn parser: xg is None (not available)", snap["stats"]["home"]["xg"] is None)
check("espn parser: goal event", snap["events"] and snap["events"][0]["type"] == "goal")

# failover: fotmob dies, espn serves
match = {"id": "1", "home": "Real Salt Lake", "away": "Demo United", "date": "2026-11-01T01:00:00Z", "state": "in"}
common.write_json(common.path("schedule.json"), {"matches": [match]})
def boom(*a, **k): raise RuntimeError("simulated fotmob outage")
S.fotmob_summary = boom
S.espn_summary = lambda eid: S.espn_parse_summary(ESPN_FIX, eid)
live.run("1")
lv = common.read_json(common.path("live.json"))
check("failover: served by espn as backup 1", lv["snapshot"]["source"] == "espn" and lv["snapshot"]["source_role"] == "backup 1")
check("failover: chain shows fotmob failed", lv["chain"][0] == {"source": "fotmob", "ok": False, "error": "simulated fotmob outage"})
htr = common.read_json(common.path("halftime.json"))
check("failover: halftime report built from backup", htr and htr["source"] == "espn" and htr["has_xg"] is False)
check("halftime: cards exist and all labeled", htr["cards"] and all(c["confidence"] in ("Measured", "Inference") for c in htr["cards"]))
check("halftime: every card has data, meaning, watch", all(c["data"] and c["meaning"] and c["watch"] for c in htr["cards"]))
check("halftime: xG-dependent card absent when xG null", not any("xg_good" in c["id"] for c in htr["cards"]))
check("health.json records fotmob failure", common.read_json(common.path("health.json"))["sources"]["fotmob"]["ok"] is False)
st = common.read_json(common.path("live_state.json"))
check("halftime frozen once", st["ht_frozen"] is True)

# all sources fail: previous data kept, no crash
S.espn_summary = boom
before = common.read_json(common.path("halftime.json"))
live.run("1")
check("all fail: halftime report preserved", common.read_json(common.path("halftime.json")) == before)
check("all fail: failure recorded in live.json", "all_failed_at" in common.read_json(common.path("live.json")))

# rules skip null inputs
prof = common.read_json(common.path("profiles.json"))
t = json.loads(json.dumps(prof));
for tm in t["teams"].values():
    for k in ("xg", "xg_ag", "ppda"): tm["metrics"].pop(k, None)
cards = rules.season_cards(t, "Real Salt Lake"); mu = rules.matchup(t, "Real Salt Lake", "Demo United")
check("rules: skip cleanly without xG and PPDA", not any(c["id"] in ("vuln_xg", "finishing", "press_high", "press_low") for c in cards) and isinstance(mu["keys"], list))

# playoffs: window extends for extra time, norms exclude playoff games, form includes them
import schedule as SC
k = dt.datetime(2026, 11, 20, 3, 0, tzinfo=dt.timezone.utc)
sched = {"matches": [{"id": "p1", "date": k.isoformat(), "stage": "playoff"}]}
check("playoff window still active at +190 min", SC.active_match(sched, k + dt.timedelta(minutes=190)) is not None)
sched["matches"][0]["stage"] = "regular"
check("regular window closed at +190 min", SC.active_match(sched, k + dt.timedelta(minutes=190)) is None)
def mk(i, stage, shots):
    st = {k_: None for k_ in S.EMPTY_STATS}; st.update(possession_pct=50, shots=shots, passes=400, crosses=10)
    return {"id": str(i), "date": f"2026-0{1 + i}-01T00:00:00Z", "stage": stage, "home": "A", "away": "B", "hs": 1, "as": 0, "stats": {"home": dict(st), "away": dict(st)}}
tm = profiles.build([mk(1, "regular", 10), mk(2, "regular", 10), mk(3, "playoff", 30)])
check("norms exclude playoff game", abs(tm["A"]["metrics"]["shots"]["v"] - 10) < 1e-9)
check("form includes playoff game", len(tm["A"]["form"]["last5"]["results"]) == 3 and tm["A"]["playoff_games"] == 1)

# no em dashes in any generated copy or app files
bad = []
for root in (os.path.join(ROOT, "web"), os.path.join(ROOT, "scripts"), common.DATA):
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".js", ".html", ".css", ".py", ".json")):
                if chr(0x2014) in open(os.path.join(dp, f), encoding="utf-8").read(): bad.append(f)
check("no em dashes in app, scripts or generated data " + str(bad), not bad)

print(f"\n{ok} passed, {fail} failed"); shutil.rmtree(TMP, ignore_errors=True); sys.exit(1 if fail else 0)
