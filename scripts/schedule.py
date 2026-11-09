"""Daily job: read the MLS season feed, keep RSL fixtures, write data/schedule.json."""
import datetime as dt
from common import *
import sources as S


def parse(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def build(events):
    mine = [e for e in events if S.same_team(e["home"], RSL_NAME) or S.same_team(e["away"], RSL_NAME)]
    mine.sort(key=lambda e: e["date"])
    now = dt.datetime.now(dt.timezone.utc)
    upcoming = [e for e in mine if parse(e["date"]) > now - dt.timedelta(minutes=130) and e["state"] != "post"]
    done = [e for e in mine if e["state"] == "post"]
    return {"generated_at": now_iso(), "season": SEASON, "matches": mine,
            "next": upcoming[0] if upcoming else None, "last_completed": done[-1] if done else None}


def active_match(sched, now=None, before_min=15, after_min=135):
    """The RSL match in progress (kickoff - before_min to kickoff + after_min), else None."""
    now = now or dt.datetime.now(dt.timezone.utc)
    for e in sched.get("matches", []):
        k = parse(e["date"])
        after = 210 if e.get("stage") == "playoff" else after_min   # extra time and penalties
        if k - dt.timedelta(minutes=before_min) <= now <= k + dt.timedelta(minutes=after):
            return e
    return None


def run():
    ev = S.espn_season_events()
    if not ev:
        log_health("espn", False, "schedule: no events returned, keeping previous schedule")
        raise SystemExit("no events")
    sched = build(ev)
    write_json(path("schedule.json"), sched)
    log_health("espn", True, f"schedule {len(sched['matches'])} RSL matches")
    print("next:", sched["next"] and (sched["next"]["home"], sched["next"]["away"], sched["next"]["date"]))


if __name__ == "__main__":
    run()
