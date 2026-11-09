"""Live poller. Exits immediately unless an RSL match is in progress (or --match-id given).
Fallback chain: FotMob, then ESPN, then API-Football. First success wins.
Writes data/live.json every poll, freezes the first-half snapshot at halftime, builds data/halftime.json.

Test failover: FORCE_FAIL=fotmob python scripts/live.py --match-id ID   (comma list allowed)
"""
import argparse
from common import *
import rules, schedule as SC
import sources as S

CHAIN = [("fotmob", "primary"), ("espn", "backup 1"), ("api-football", "backup 2")]


def fetch_chain(match):
    forced = {x.strip() for x in os.environ.get("FORCE_FAIL", "").split(",") if x.strip()}
    tried = []
    for name, role in CHAIN:
        try:
            if name in forced:
                raise RuntimeError("forced failure (test)")
            if name == "fotmob":
                snap = S.fotmob_summary(match["home"], match["away"], match["date"])
            elif name == "espn":
                snap = S.espn_summary(match["id"])
            else:
                snap = S.apif_summary(match["home"], match["away"], match["date"])
            snap["source_role"] = role
            log_health(name, True, "live ok")
            tried.append({"source": name, "ok": True})
            return snap, tried
        except Exception as ex:
            log_health(name, False, ex)
            tried.append({"source": name, "ok": False, "error": str(ex)[:160]})
    return None, tried


def period_of(snap):
    if snap.get("period"):
        return snap["period"]
    m = snap.get("minute")
    return 1 if (m is not None and m <= 45) else 2


def make_halftime(snap, prof, note=""):
    rsl_side = "home" if snap["teams"]["home"].get("is_rsl") else "away"
    out = rules.halftime(snap, prof, rsl_side)
    out.update({"generated_at": now_iso(), "match_id": snap["match_id"], "source": snap["source"],
                "source_role": snap.get("source_role", ""), "snapshot_at": snap["fetched_at"], "note": note,
                "has_xg": any(snap["stats"][s].get("xg") is not None for s in ("home", "away")),
                "has_shot_map": bool(snap.get("shots")), "shots": snap.get("shots") or [],
                "attack_side": {s: snap["stats"][s].get("attack_side") for s in ("home", "away")},
                "minute": snap.get("minute")})
    return out


def run(match_id=None):
    sched = read_json(path("schedule.json"), {})
    prof = read_json(path("profiles.json"))
    match = next((m for m in sched.get("matches", []) if m["id"] == str(match_id)), None) if match_id else SC.active_match(sched)
    if not match:
        print("No RSL match in progress, exiting.")
        return False
    state = read_json(path("live_state.json"), {})
    if state.get("match_id") != match["id"]:
        state = {"match_id": match["id"], "ht_frozen": False}
    snap, tried = fetch_chain(match)
    if not snap:
        live = read_json(path("live.json"), {})
        live.update({"chain": tried, "all_failed_at": now_iso()})
        write_json(path("live.json"), live)
        print("All sources failed; kept previous data.")
        return
    write_json(path("live.json"), {"match": match, "snapshot": snap, "chain": tried, "updated_at": now_iso()})
    if snap["status"] == "live" and period_of(snap) == 1:
        write_json(path("first_half_latest.json"), snap)
    if not state["ht_frozen"] and prof:
        if snap["status"] == "ht":
            write_json(path("ht_snapshot.json"), snap)
            write_json(path("halftime.json"), make_halftime(snap, prof))
            state["ht_frozen"] = True
            print("Halftime report built from", snap["source"])
        elif snap["status"] == "live" and period_of(snap) == 2:
            fh = read_json(path("first_half_latest.json"))
            if fh and fh.get("match_id") == snap["match_id"]:
                write_json(path("halftime.json"), make_halftime(fh, prof, "Built from the last first-half poll (halftime poll was missed)."))
                state["ht_frozen"] = True
    write_json(path("live_state.json"), state)
    print(f"live ok via {snap['source']} status={snap['status']} min={snap.get('minute')}")


if __name__ == "__main__":
    import sys
    ap = argparse.ArgumentParser(); ap.add_argument("--match-id")
    sys.exit(3 if run(ap.parse_args().match_id) is False else 0)  # exit 3 = no match, workflow stops looping
